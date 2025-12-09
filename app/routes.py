import os
from flask import redirect, request, session, url_for, render_template, jsonify
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError
from app import app
from app import database
from app.utils.supabase_client import supabase

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
    return render_template('login.html',
                         supabase_url=os.environ.get('SUPABASE_URL'), 
                         supabase_key=os.environ.get('SUPABASE_KEY'))

@app.route('/login')
def login():
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_KEY')
    
    # Pass Supabase config to template
    return render_template('login.html', 
                         supabase_url=url, 
                         supabase_key=key)

@app.route('/auth/callback')
def auth_callback():
    # Render the callback page which handles the hash fragment
    return render_template('callback.html',
                         supabase_url=os.environ.get('SUPABASE_URL'), 
                         supabase_key=os.environ.get('SUPABASE_KEY'))

@app.route('/api/auth/session', methods=['POST'])
def save_session():
    try:
        data = request.get_json()
        user = data.get('user')
        # ... (rest of extraction)
        # Extract tokens
        supabase_jwt = data.get('access_token') # Supabase JWT
        access_token = data.get('provider_token') # Google Access Token
        refresh_token = data.get('provider_refresh_token') # Google Refresh Token
        
        if not user or not access_token:
            return jsonify({'status': 'error', 'message': 'Missing user or token data'}), 400
            
        user_id = user['id']
        
        # Extract Google ID
        google_id = None
        if user.get('identities'):
            # Try to find Google identity
            for identity in user['identities']:
                if identity['provider'] == 'google':
                    google_id = identity['identity_data'].get('sub') or identity['id']
                    break
        
        # Save tokens to database
        save_result = database.save_user_tokens(
            user_id=user_id,
            google_id=google_id,
            channel_id=None, # Will fetch below
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=None,
            jwt=supabase_jwt # Pass JWT for RLS
        )
        
        if not save_result:
             print("[WARN] Failed to save user tokens in database (first attempt).")
        
        # Fetch Channel ID
        try:
            import google.oauth2.credentials
            creds = google.oauth2.credentials.Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=creds)
            response = youtube.channels().list(mine=True, part='id').execute()
            if response['items']:
                channel_id = response['items'][0]['id']
                database.save_user_tokens(
                    user_id=user_id,
                    google_id=google_id,
                    channel_id=channel_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expiry=None,
                    jwt=supabase_jwt # Pass JWT for RLS
                )
        except Exception as e:
            print(f"[WARN] Failed to fetch channel ID: {e}")

        # Set Flask Session
        session['user_id'] = user_id
        
        return jsonify({'status': 'success', 'redirect_url': url_for('videos')})
        
    except Exception as e:
        print(f"[ERROR] Save session failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    # We should also sign out from Supabase on the client side, 
    # but for now clearing the server session is enough to protect backend routes.
    # Ideally, logout should also be a client-side action or redirect to a page that signs out.
    return redirect(url_for('index'))


@app.route('/videos')
def videos():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # Verify user exists in our DB (tokens saved)
    if not database.get_user(session['user_id']):
        session.clear()
        return redirect(url_for('index'))
    
    try:
        sort_by = request.args.get('sort', 'date_desc')
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
    
    sort_by = request.args.get('sort', 'date_desc')
    comments_data = youtube_service.get_video_comments(session['user_id'], video_id, sort_by)
    video_details = youtube_service.get_video_details(session['user_id'], video_id)
    video_title = video_details.get('title', 'Unknown Video')
    
    return render_template('comments.html', 
                         comments=comments_data['comments'],
                         video_id=video_id,
                         video=video_details,
                         video_title=video_title,
                         current_sort=sort_by,
                         reply_stats=comments_data['stats'])

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
        original_comment = data.get('original_comment', '')
        ai_suggestion = data.get('ai_suggestion', '')
        
        database.log_reply(
            user_id=session['user_id'],
            video_id=data.get('video_id', ''),
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
        import traceback
        tb = traceback.format_exc()
        print(tb) # Still print to server log
        return {'status': 'error', 'message': f"{str(e)}\n\nTraceback:\n{tb}"}, 500

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
        
        youtube_service.rate_comment(session['user_id'], comment_id, rating)
        return {'status': 'success'}
    except RefreshError:
        session.clear()
        return {'status': 'error', 'message': 'Token expired, please log in again'}, 401
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/mark_complete', methods=['POST'])
def mark_complete():
    if 'user_id' not in session:
        return {'status': 'error', 'message': 'Unauthorized'}, 401
    
    if not database.get_user(session['user_id']):
        session.clear()
        return {'status': 'error', 'message': 'User not found'}, 401
    
    try:
        data = request.get_json()
        comment_id = data.get('comment_id')
        
        # Get user tokens to retrieve JWT
        user_data = database.get_user(session['user_id'])
        jwt = user_data.get('jwt') if user_data else None

        if database.mark_thread_complete(session['user_id'], comment_id, jwt=jwt):
            return {'status': 'success'}
        else:
            return {'status': 'error', 'message': 'Failed to mark complete'}, 500
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500


@app.route('/unmark_complete', methods=['POST'])
def unmark_complete():
    if 'user_id' not in session:
        return {'status': 'error', 'message': 'Unauthorized'}, 401
    
    if not database.get_user(session['user_id']):
        session.clear()
        return {'status': 'error', 'message': 'User not found'}, 401
    
    try:
        data = request.get_json()
        comment_id = data.get('comment_id')
        
        # Get user tokens to retrieve JWT
        user_data = database.get_user(session['user_id'])
        jwt = user_data.get('jwt') if user_data else None

        if database.delete_thread_state(session['user_id'], comment_id, jwt=jwt):
            return {'status': 'success'}
        else:
            return {'status': 'error', 'message': 'Failed to unmark complete'}, 500
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500
