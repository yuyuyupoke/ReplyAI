from googleapiclient.discovery import build
from app.services import auth
from app import database

from googleapiclient.errors import HttpError

def get_youtube_client(user_id):
    user = database.get_user(user_id)
    creds = auth.get_credentials_from_user(user)
    return build('youtube', 'v3', credentials=creds)

from datetime import datetime, timedelta

def get_video_stats(user_id, video_id):
    """
    Helper to get stats for a video.
    Used by get_recent_videos for sorting.
    """
    # Limit max_pages to 5 (500 comments) to avoid excessive API usage/latency during sort
    data = get_video_comments(user_id, video_id, sort_by='date_desc', max_pages=5)
    stats = data['stats']
    return stats['unreplied'], stats

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
            unreplied_count, _ = get_video_stats(user_id, video['id'])
            video['unreplied_count'] = unreplied_count
        
        # Sort by unreplied count descending
        videos.sort(key=lambda x: x['unreplied_count'], reverse=True)

    return videos

def get_video_comments(user_id, video_id, sort_by='date_desc', max_pages=None):
    youtube = get_youtube_client(user_id)
    user = database.get_user(user_id)
    my_channel_id = user['channel_id']
    jwt = user.get('jwt')

    # Fetch completed threads
    completed_thread_ids = set(database.get_completed_threads(user_id, jwt=jwt))

    unreplied_comments = []
    replied_comments = []
    pending_comments = []
    
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
                return {'comments': [], 'stats': {'total': 0, 'replied': 0, 'pending': 0, 'unreplied': 0, 'rate': 0}}
            raise e

        page_count += 1


        for item in response['items']:
            top_level_comment = item['snippet']['topLevelComment']
            top_level_snippet = top_level_comment['snippet']
            reply_count = item['snippet']['totalReplyCount']
            
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
            
            # Check if manually completed
            is_manually_completed = top_level_comment['id'] in completed_thread_ids
            
            # Process replies
            raw_replies = item.get('replies', {}).get('comments', [])
            processed_replies = []
            for reply in raw_replies:
                rs = reply['snippet']
                is_mine_reply = rs['authorChannelId']['value'] == my_channel_id
                processed_replies.append({
                    'id': reply['id'],
                    'text': rs.get('textOriginal', rs['textDisplay']),
                    'author_name': rs['authorDisplayName'],
                    'author_image': rs['authorProfileImageUrl'],
                    'published_at': rs['publishedAt'],
                    'updated_at': rs['updatedAt'],
                    'like_count': rs.get('likeCount', 0),
                    'video_id': video_id,
                    'is_mine': is_mine_reply
                })
            # Sort replies by date (oldest first for conversation flow)
            processed_replies.sort(key=lambda x: x['published_at'])

            comment_data = {
                'id': top_level_comment['id'], # Use TopLevelComment ID, not Thread ID
                'text': top_level_snippet.get('textOriginal', top_level_snippet['textDisplay']), # Prefer textOriginal
                'author_name': top_level_snippet['authorDisplayName'],
                'author_image': top_level_snippet['authorProfileImageUrl'],
                'published_at': top_level_snippet['publishedAt'],
                'updated_at': top_level_snippet['updatedAt'],
                'like_count': top_level_snippet.get('likeCount', 0),
                'viewer_rating': top_level_snippet.get('viewerRating', 'none'), # Fetch viewer rating
                'reply_count': reply_count,
                'video_id': video_id,
                'is_replied': replied_by_me,
                'is_manually_completed': is_manually_completed,
                'replies': processed_replies, # Use processed replies
                'viewer_rating': top_level_snippet.get('viewerRating', 'none'),
                'is_edited': top_level_snippet['updatedAt'] != top_level_snippet['publishedAt']
            }
            
            if replied_by_me:
                replied_comments.append(comment_data)
            elif is_manually_completed:
                pending_comments.append(comment_data)
            else:
                unreplied_comments.append(comment_data)
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
            
    # Sort each list
    def sort_comments(comments, sort_key):
        if sort_key == 'date_desc':
            return sorted(comments, key=lambda x: x['published_at'], reverse=True)
        elif sort_key == 'date_asc':
            return sorted(comments, key=lambda x: x['published_at'])
        elif sort_key == 'likes_desc':
            return sorted(comments, key=lambda x: x['like_count'], reverse=True)
        else:
            # Default to date_desc
            return sorted(comments, key=lambda x: x['published_at'], reverse=True)

    unreplied_comments = sort_comments(unreplied_comments, sort_by)
    pending_comments = sort_comments(pending_comments, sort_by)
    replied_comments = sort_comments(replied_comments, sort_by)

    # Combine: Unreplied -> Pending -> Replied
    combined_comments = unreplied_comments + pending_comments + replied_comments

    # Calculate stats
    unreplied_count = len(unreplied_comments)
    pending_count = len(pending_comments)
    replied_count = len(replied_comments)
    total_comments = unreplied_count + pending_count + replied_count
    reply_rate = 0
    if total_comments > 0:
        reply_rate = int((replied_count / total_comments) * 100)
        
    if total_comments > 0:
        reply_rate = int((replied_count / total_comments) * 100)
        
    return {
        'comments': combined_comments,
        'stats': {
            'total': total_comments,
            'replied': replied_count,
            'pending': pending_count,
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
    
    # Auto-clear "pending" status if it exists
    try:
        user = database.get_user(user_id)
        jwt = user.get('jwt')
        database.delete_thread_state(user_id, parent_id, jwt=jwt)
    except Exception as e:
        print(f"[WARN] Failed to auto-clear thread state: {e}")

    return response

def delete_comment(user_id, comment_id):
    youtube = get_youtube_client(user_id)
    youtube.comments().delete(id=comment_id).execute()

# rate_comment function removed due to API limitations
