import random
from datetime import datetime, timedelta

def get_channel_info(user_id):
    return {
        'name': 'Dev User (Mock)',
        'icon': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Felix',
        'subscriber_count': 12345
    }

def get_recent_videos(user_id, limit=200, sort_by='date_desc'):
    videos = []
    base_date = datetime.now()
    
    titles = [
        "【衝撃】AIを使って業務効率化してみた結果www",
        "Pythonで自動化ツールを作る方法 #1",
        "起業して1年で学んだこと全て話します",
        "Vlog: エンジニアの1日 - 東京編",
        "【初心者向け】プログラミング学習のロードマップ2025"
    ]
    
    for i in range(10):
        vid_id = f"mock_vid_{i}"
        published_at = (base_date - timedelta(days=i*2)).isoformat()
        
        videos.append({
            'id': vid_id,
            'title': titles[i % len(titles)] + f" (Vol.{i+1})",
            'thumbnail': f"https://picsum.photos/seed/{vid_id}/320/180",
            'published_at': published_at,
            'view_count': random.randint(100, 10000),
            'watch_time_mins': random.randint(10, 500),
            'avg_watch_time_sec': random.randint(60, 600)
        })
        
    # Sorting (simplified version of real service)
    if sort_by == 'date_desc':
        videos.sort(key=lambda x: x['published_at'], reverse=True)
    elif sort_by == 'date_asc':
        videos.sort(key=lambda x: x['published_at'])
    elif sort_by == 'views_desc':
        videos.sort(key=lambda x: x['view_count'], reverse=True)
        
    return videos

def get_video_comments(user_id, video_id, sort_by='date_desc'):
    unreplied = []
    replied = []
    
    # Mock comments
    comments_text = [
        "すごく参考になりました！",
        "これってどうやるんですか？詳しく知りたいです。",
        "いつも見てます！応援してます🔥",
        "音声が少し聞き取りにくいかも...",
        "次の動画も楽しみにしてます！"
    ]
    
    # Generate some unreplied comments
    for i in range(5):
        cid = f"mock_comment_{video_id}_{i}"
        unreplied.append({
            'id': cid,
            'text': comments_text[i % len(comments_text)],
            'author_name': f"User_{i}",
            'author_image': f"https://api.dicebear.com/7.x/avataaars/svg?seed={i}",
            'published_at': (datetime.now() - timedelta(hours=i)).isoformat(),
            'like_count': random.randint(0, 10),
            'viewer_rating': random.choice(['like', 'none', 'none', 'none']), # Mostly none, some liked
            'video_id': video_id,
            'is_replied': False
        })
        
    # Generate some replied comments
    for i in range(3):
        cid = f"mock_replied_{video_id}_{i}"
        replied.append({
            'id': cid,
            'text': f"過去の動画についての質問です ({i})",
            'author_name': f"Fan_{i}",
            'author_image': f"https://api.dicebear.com/7.x/avataaars/svg?seed=fan{i}",
            'published_at': (datetime.now() - timedelta(days=1, hours=i)).isoformat(),
            'like_count': random.randint(5, 20),
            'viewer_rating': 'like', # Assume we liked replied comments
            'video_id': video_id,
            'is_replied': True,
            'replies': [{
                'id': f"reply_{cid}",
                'author_name': "Dev User (Mock)",
                'author_image': "https://api.dicebear.com/7.x/avataaars/svg?seed=Felix",
                'text': "コメントありがとうございます！その件については...",
                'published_at': datetime.now().isoformat(),
                'is_mine': True
            }]
        })
        
    # Calculate stats
    unreplied_count = len(unreplied)
    replied_count = len(replied)
    total_comments = unreplied_count + replied_count
    reply_rate = 0
    if total_comments > 0:
        reply_rate = int((replied_count / total_comments) * 100)

    return {
        'comments': unreplied + replied,
        'stats': {
            'total': total_comments,
            'replied': replied_count,
            'unreplied': unreplied_count,
            'rate': reply_rate
        }
    }

def get_video_details(user_id, video_id):
    return {
        'id': video_id,
        'title': f"Mock Video Title for {video_id}",
        'thumbnail': f"https://picsum.photos/seed/{video_id}/320/180"
    }

def get_aggregated_reply_stats(user_id, limit=5):
    return {
        'total': 100,
        'replied': 10,
        'unreplied': 90,
        'rate': 10
    }

def post_reply(user_id, parent_id, text):
    print(f"[MOCK] Posted reply to {parent_id}: {text}")
    return {
        'id': f"mock_reply_{random.randint(1000,9999)}",
        'snippet': {
            'authorDisplayName': 'Dev User (Mock)',
            'authorProfileImageUrl': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Felix',
            'textDisplay': text,
            'publishedAt': datetime.now().isoformat()
        }
    }

def delete_comment(user_id, comment_id):
    print(f"[MOCK] Deleted comment {comment_id}")
    return

def rate_comment(user_id, comment_id, rating):
    print(f"[MOCK] Rated comment {comment_id} as {rating}")
    return
