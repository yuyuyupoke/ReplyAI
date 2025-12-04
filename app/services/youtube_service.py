from googleapiclient.discovery import build
from app.services import auth
from app import database

from googleapiclient.errors import HttpError

def get_youtube_client(user_id):
    user = database.get_user(user_id)
    creds = auth.get_credentials_from_user(user)
    return build('youtube', 'v3', credentials=creds)

from datetime import datetime, timedelta

def get_analytics_client(user_id):
    user = database.get_user(user_id)
    creds = auth.get_credentials_from_user(user)
    return build('youtubeAnalytics', 'v2', credentials=creds)

def get_channel_info(user_id):
    youtube = get_youtube_client(user_id)
    response = youtube.channels().list(
        mine=True,
        part='snippet,statistics'
    ).execute()
    
    if not response['items']:
        return None
    
    channel = response['items'][0]
    return {
        'name': channel['snippet']['title'],
        'icon': channel['snippet']['thumbnails']['default']['url'],
        'subscriber_count': int(channel['statistics'].get('subscriberCount', 0))
    }

def get_recent_videos(user_id, limit=200, sort_by='date_desc'):
    youtube = get_youtube_client(user_id)
    
    # Special handling for 'unreplied_desc' to save quota
    # We only fetch top 50 videos and check their reply status
    if sort_by == 'unreplied_desc':
        limit = 50

    # 1. Get Uploads playlist ID
    channels_response = youtube.channels().list(
        mine=True,
        part='contentDetails'
    ).execute()
    uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    # 2. Get recent videos from playlist (Loop for limit)
    playlist_items = []
    next_page_token = None
    
    while len(playlist_items) < limit:
        request_limit = min(50, limit - len(playlist_items))
        response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part='snippet,contentDetails',
            maxResults=request_limit,
            pageToken=next_page_token
        ).execute()
        
        playlist_items.extend(response['items'])
        next_page_token = response.get('nextPageToken')
        
        if not next_page_token:
            break

    if not playlist_items:
        return []

    video_ids = [item['contentDetails']['videoId'] for item in playlist_items]
    
    # 3. Get Video Statistics (View Count) - Batching
    stats_map = {}
    duration_map = {}
    
    # Process in chunks of 50
    for i in range(0, len(video_ids), 50):
        chunk_ids = video_ids[i:i+50]
        stats_response = youtube.videos().list(
            part='statistics,contentDetails',
            id=','.join(chunk_ids)
        ).execute()
        
        for item in stats_response['items']:
            stats_map[item['id']] = item['statistics']
            duration_map[item['id']] = item['contentDetails']['duration']

    # 4. Get Analytics Data (Watch Time) - Batching
    analytics_map = {}
    try:
        analytics = get_analytics_client(user_id)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = '2010-01-01'
        
        # Process in chunks of 50 to avoid URL length limits
        for i in range(0, len(video_ids), 50):
            chunk_ids = video_ids[i:i+50]
            
            try:
                analytics_response = analytics.reports().query(
                    ids='channel==MINE',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='estimatedMinutesWatched,averageViewDuration',
                    dimensions='video',
                    filters=f'video=={",".join(chunk_ids)}'
                ).execute()
                
                if 'rows' in analytics_response:
                    for row in analytics_response['rows']:
                        vid = row[0]
                        analytics_map[vid] = {
                            'estimatedMinutesWatched': row[1],
                            'averageViewDuration': row[2]
                        }
            except Exception as e:
                print(f"[WARN] Analytics batch failed: {e}")
                
    except Exception as e:
        print(f"[DEBUG] Error fetching analytics: {type(e).__name__}: {e}")
        pass

    videos = []
    for item in playlist_items:
        vid = item['contentDetails']['videoId']
        snippet = item['snippet']
        stats = stats_map.get(vid, {})
        analytics = analytics_map.get(vid, {'estimatedMinutesWatched': 0, 'averageViewDuration': 0})
        
        video_data = {
            'id': vid,
            'title': snippet['title'],
            'thumbnail': snippet['thumbnails'].get('medium', snippet['thumbnails'].get('default'))['url'],
            'published_at': snippet['publishedAt'],
            'view_count': int(stats.get('viewCount', 0)),
            'watch_time_mins': int(analytics['estimatedMinutesWatched']),
            'avg_watch_time_sec': int(analytics['averageViewDuration']),
            'unreplied_count': 0 # Default
        }
        videos.append(video_data)

    # 5. Sorting
    if sort_by == 'date_desc':
        videos.sort(key=lambda x: x['published_at'], reverse=True)
    elif sort_by == 'date_asc':
        videos.sort(key=lambda x: x['published_at'])
    elif sort_by == 'views_desc':
        videos.sort(key=lambda x: x['view_count'], reverse=True)
    elif sort_by == 'watch_time_desc':
        videos.sort(key=lambda x: x['watch_time_mins'], reverse=True)
    elif sort_by == 'unreplied_desc':
        # Fetch comment stats for each video to calculate unreplied count
        print("[INFO] Sorting by unreplied_desc: Fetching comments for top 50 videos...")
        for video in videos:
            try:
                # Fetch only 1 page of comments to save quota
                data = get_video_comments(user_id, video['id'], max_pages=1)
                video['unreplied_count'] = data['stats']['unreplied']
            except Exception as e:
                print(f"[WARN] Failed to fetch comments for video {video['id']}: {e}")
                video['unreplied_count'] = 0
        
        # Sort by unreplied count descending
        videos.sort(key=lambda x: x['unreplied_count'], reverse=True)

    return videos

def get_video_comments(user_id, video_id, sort_by='date_desc', max_pages=None):
    youtube = get_youtube_client(user_id)
    user = database.get_user(user_id)
    my_channel_id = user['channel_id']

    unreplied_comments = []
    replied_comments = []
    
    next_page_token = None
    page_count = 0
    
    while True:
        if max_pages and page_count >= max_pages:
            break
            
        try:
            response = youtube.commentThreads().list(
                part='snippet,replies',
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
                textFormat='plainText'
            ).execute()
        except HttpError as e:
            if e.resp.status == 403 and 'commentsDisabled' in str(e):
                return {'unreplied': [], 'replied': [], 'stats': {'total': 0, 'replied': 0, 'unreplied': 0, 'rate': 0}}
            raise e

        page_count += 1


        for item in response['items']:
            top_level_comment = item['snippet']['topLevelComment']
            top_level_snippet = top_level_comment['snippet']
            
            # Filter A: Top level comment
            # Filter B: Not from me
            if top_level_snippet['authorChannelId']['value'] == my_channel_id:
                continue
            
            # Check if replied by me
            replied_by_me = False
            if 'replies' in item:
                for reply in item['replies']['comments']:
                    if reply['snippet']['authorChannelId']['value'] == my_channel_id:
                        replied_by_me = True
                        break
            
            comment_data = {
                'id': top_level_comment['id'], # Use TopLevelComment ID, not Thread ID
                'text': top_level_snippet['textDisplay'],
                'author_name': top_level_snippet['authorDisplayName'],
                'author_image': top_level_snippet['authorProfileImageUrl'],
                'published_at': top_level_snippet['publishedAt'],
                'like_count': top_level_snippet.get('likeCount', 0),
                'viewer_rating': top_level_snippet.get('viewerRating', 'none'), # Fetch viewer rating
                'video_id': video_id
            }
            
            if replied_by_me:
                # Include replies for replied comments
                comment_data['replies'] = []
                if 'replies' in item:
                    for reply in item['replies']['comments']:
                        reply_snippet = reply['snippet']
                        comment_data['replies'].append({
                            'id': reply['id'],
                            'author_name': reply_snippet['authorDisplayName'],
                            'author_image': reply_snippet['authorProfileImageUrl'],
                            'text': reply_snippet['textDisplay'],
                            'published_at': reply_snippet['publishedAt'],
                            'is_mine': reply_snippet['authorChannelId']['value'] == my_channel_id
                        })
                print(f"[DEBUG] Replied comment {item['id']}: {len(comment_data['replies'])} replies")
                for idx, r in enumerate(comment_data['replies']):
                    print(f"[DEBUG]   Reply {idx}: {r['author_name'][:20]}... is_mine={r['is_mine']}")
                replied_comments.append(comment_data)
            else:
                unreplied_comments.append(comment_data)
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
            
    # Sorting
    def sort_comments(comments, sort_key):
        if sort_key == 'date_desc':
            comments.sort(key=lambda x: x['published_at'], reverse=True)
        elif sort_key == 'date_asc':
            comments.sort(key=lambda x: x['published_at'])
        elif sort_key == 'likes_desc':
            comments.sort(key=lambda x: x['like_count'], reverse=True)

    sort_comments(unreplied_comments, sort_by)
    sort_comments(replied_comments, sort_by)
    
    # Mark status
    for c in unreplied_comments:
        c['is_replied'] = False
    for c in replied_comments:
        c['is_replied'] = True

    # Combine: Unreplied first, then Replied
    combined_comments = unreplied_comments + replied_comments

    # Calculate stats
    unreplied_count = len(unreplied_comments)
    replied_count = len(replied_comments)
    total_comments = unreplied_count + replied_count
    reply_rate = 0
    if total_comments > 0:
        reply_rate = int((replied_count / total_comments) * 100)

    return {
        'comments': combined_comments,
        'stats': {
            'total': total_comments,
            'replied': replied_count,
            'unreplied': unreplied_count,
            'rate': reply_rate
        }
    }

def get_video_details(user_id, video_id):
    youtube = get_youtube_client(user_id)
    response = youtube.videos().list(
        part='snippet',
        id=video_id
    ).execute()
    
    if not response['items']:
        return None
        
    snippet = response['items'][0]['snippet']
    return {
        'id': video_id,
        'title': snippet['title'],
        'thumbnail': snippet['thumbnails'].get('medium', snippet['thumbnails'].get('default'))['url']
    }

def get_aggregated_reply_stats(user_id, limit=5):
    """
    Fetches comments for the latest 'limit' videos to estimate reply rate.
    Costs 'limit' units (1 per video).
    """
    videos = get_recent_videos(user_id, limit=limit)
    total_replied = 0
    total_unreplied = 0
    
    for video in videos:
        try:
            data = get_video_comments(user_id, video['id'])
            stats = data['stats']
            total_replied += stats['replied']
            total_unreplied += stats['unreplied']
        except Exception:
            pass
            
    total = total_replied + total_unreplied
    rate = 0
    if total > 0:
        rate = int((total_replied / total) * 100)
        
    return {
        'total': total,
        'replied': total_replied,
        'unreplied': total_unreplied,
        'rate': rate
    }

def post_reply(user_id, parent_id, text):
    youtube = get_youtube_client(user_id)
    response = youtube.comments().insert(
        part='snippet',
        body={
            'snippet': {
                'parentId': parent_id,
                'textOriginal': text
            }
        }
    ).execute()
    return response

def delete_comment(user_id, comment_id):
    youtube = get_youtube_client(user_id)
    youtube.comments().delete(id=comment_id).execute()

from google.auth.transport.requests import AuthorizedSession

def rate_comment(user_id, comment_id, rating):
    """
    rating: 'like', 'dislike', 'none'
    """
    print(f"[DEBUG] rate_comment called with user_id={user_id}, comment_id={comment_id}, rating={rating}")
    user = database.get_user(user_id)
    print(f"[DEBUG] user found: {user['google_id'] if user else 'None'}")
    creds = auth.get_credentials_from_user(user)
    print(f"[DEBUG] creds created: {creds.valid}")
    authed_session = AuthorizedSession(creds)
    
    url = 'https://www.googleapis.com/youtube/v3/comments/setRating'
    params = {
        'id': comment_id,
        'rating': rating
    }
    
    print(f"[DEBUG] rate_comment: POST {url} params={params}")
    response = authed_session.post(url, params=params)
    print(f"[DEBUG] rate_comment response: {response.status_code} {response.text}")
    
    if response.status_code != 204:
        # 204 No Content is expected for success
        raise Exception(f"Failed to rate comment: {response.status_code} {response.text}")
