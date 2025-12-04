import os
from flask import redirect, request, session, url_for, render_template, jsonify
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError
from app import app
from app import database
from app.services import auth

# Import services based on config
if app.config['USE_MOCK_DATA']:
    from app.services import mock_youtube_service as youtube_service
else:
    from app.services import youtube_service

from app.services import ai_service

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('videos'))
    return render_template('login.html')

@app.route('/login')
def login():
    flow = auth.get_flow(url_for('oauth2callback', _external=True))
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/dev_login')
def dev_login():
    if not app.config['USE_MOCK_DATA']:
        return "Dev login is disabled in production", 403
    
    # Create or get a mock user
    mock_google_id = "mock_user_001"
    user_id = database.save_user(
        google_id=mock_google_id,
        channel_id="mock_channel_id",
        access_token="mock_access_token",
        refresh_token="mock_refresh_token",
        expires_in="2099-12-31T23:59:59"
    )
    
    session['user_id'] = user_id
    return redirect(url_for('videos'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/oauth2callback')
def oauth2callback():
    if 'state' not in session:
        return redirect(url_for('login'))
        
    state = session['state']
    flow = auth.get_flow(url_for('oauth2callback', _external=True))
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    
    # Get channel ID
    youtube = build('youtube', 'v3', credentials=credentials)
    response = youtube.channels().list(mine=True, part='id').execute()
    channel_id = response['items'][0]['id']
    
    # Save user
    user_id = database.save_user(
        google_id=channel_id, # Use channel_id as unique identifier
        channel_id=channel_id,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        expires_in=credentials.expiry.isoformat() if credentials.expiry else ''
    )
    
    session['user_id'] = user_id
    return redirect(url_for('videos'))

@app.route('/videos')
def videos():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    if not database.get_user(session['user_id']):
        session.clear()
        return redirect(url_for('index'))
    
    try:
        sort_by = request.args.get('sort', 'unreplied_desc')
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        all_videos = youtube_service.get_recent_videos(session['user_id'], sort_by=sort_by)
        channel_info = youtube_service.get_channel_info(session['user_id'])
        
        # Pagination logic
        total_videos = len(all_videos)
        total_pages = (total_videos + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        videos_subset = all_videos[start:end]
        
        # Fetch stats for each video in the subset
        for video in videos_subset:
            try:
                # Reuse get_video_comments to get stats
                # Note: This adds N API calls where N is page size (e.g. 10)
                data = youtube_service.get_video_comments(session['user_id'], video['id'])
                video['reply_stats'] = data['stats']
            except Exception as e:
                print(f"Error fetching stats for video {video['id']}: {e}")
                video['reply_stats'] = {'total': 0, 'replied': 0, 'unreplied': 0, 'rate': 0}

        reply_stats = youtube_service.get_aggregated_reply_stats(session['user_id'], limit=5)
        
        return render_template('videos.html', 
                             videos=videos_subset, 
                             current_sort=sort_by, 
                             channel_info=channel_info,
                             page=page,
                             total_pages=total_pages,
                             reply_stats=reply_stats)
    except RefreshError:
        session.clear()
        return redirect(url_for('login'))
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/comments/<video_id>')
def comments(video_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if not database.get_user(session['user_id']):
        session.clear()
        return redirect(url_for('index'))
    
    try:
        sort_by = request.args.get('sort', 'date_desc')
        comments_data = youtube_service.get_video_comments(session['user_id'], video_id, sort_by=sort_by)
        video_details = youtube_service.get_video_details(session['user_id'], video_id)
        
        return render_template('comments.html', 
                             comments=comments_data['comments'],
                             video_id=video_id,
                             video=video_details,
                             current_sort=sort_by,
                             reply_stats=comments_data['stats'])
    except RefreshError:
        session.clear()
        return redirect(url_for('login'))
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

@app.route('/post_reply', methods=['POST'])
def post_reply():
    if 'user_id' not in session:
        return {'status': 'error', 'message': 'Unauthorized'}, 401
    
    if not database.get_user(session['user_id']):
        session.clear()
        return {'status': 'error', 'message': 'User not found'}, 401
    
    data = request.get_json()
    parent_id = data.get('parent_id')
    text = data.get('reply_text')
    
    try:
        response = youtube_service.post_reply(session['user_id'], parent_id, text)
        
        # Log the reply for AI learning
        # We need original_comment and ai_suggestion from frontend to log properly
        original_comment = data.get('original_comment', '')
        ai_suggestion = data.get('ai_suggestion', '')
        
        database.log_reply(
            user_id=session['user_id'],
            video_id=data.get('video_id', ''), # Need to pass video_id from frontend
            comment_id=parent_id,
            original_comment=original_comment,
            ai_suggestion=ai_suggestion,
            final_reply=text
        )
        
        return {
            'status': 'success', 
            'id': response['id'],
            'author_image': response['snippet'].get('authorProfileImageUrl', ''),
            'author_name': response['snippet'].get('authorDisplayName', ''),
            'published_at': response['snippet'].get('publishedAt', '')
        }
    except RefreshError:
        session.clear()
        return {'status': 'error', 'message': 'Token expired, please log in again'}, 401
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/generate_reply', methods=['POST'])
def generate_reply():
    if 'user_id' not in session:
        return {'status': 'error', 'message': 'Unauthorized'}, 401
    
    if not database.get_user(session['user_id']):
        session.clear()
        return {'status': 'error', 'message': 'User not found'}, 401
    
    try:
        data = request.get_json()
        comment_text = data.get('comment')
        custom_instruction = data.get('instruction')
        
        # Get few-shot examples from database
        examples = database.get_few_shot_examples(session['user_id'])
        
        suggestions, usage = ai_service.generate_reply_suggestions(comment_text, custom_instruction, examples)
        
        if usage:
            database.log_usage(
                user_id=session['user_id'],
                input_tokens=usage['input_tokens'],
                output_tokens=usage['output_tokens'],
                model_name=usage['model_name']
            )
        
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/delete_comment', methods=['POST'])
def delete_comment():
    if 'user_id' not in session:
        return {'status': 'error', 'message': 'Unauthorized'}, 401
    
    if not database.get_user(session['user_id']):
        session.clear()
        return {'status': 'error', 'message': 'User not found'}, 401
    
    try:
        data = request.get_json()
        comment_id = data.get('comment_id')
        
        youtube_service.delete_comment(session['user_id'], comment_id)
        return {'status': 'success'}
    except RefreshError:
        session.clear()
        return {'status': 'error', 'message': 'Token expired, please log in again'}, 401
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/rate_comment', methods=['POST'])
def rate_comment():
    if 'user_id' not in session:
        return {'status': 'error', 'message': 'Unauthorized'}, 401
    
    if not database.get_user(session['user_id']):
        session.clear()
        return {'status': 'error', 'message': 'User not found'}, 401
    
    try:
        data = request.get_json()
        comment_id = data.get('comment_id')
        rating = data.get('rating') # 'like', 'dislike', 'none'
        print(f"[DEBUG] app.py rate_comment request: comment_id={comment_id}, rating={rating}")
        
        youtube_service.rate_comment(session['user_id'], comment_id, rating)
        return {'status': 'success'}
    except RefreshError:
        session.clear()
        return {'status': 'error', 'message': 'Token expired, please log in again'}, 401
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500
