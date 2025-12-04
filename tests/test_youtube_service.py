import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import youtube_service

class TestYouTubeService(unittest.TestCase):

    @patch('youtube_service.get_youtube_client')
    @patch('youtube_service.database.get_user')
    def test_get_channel_info(self, mock_get_user, mock_get_client):
        # Mock setup
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        
        mock_response = {
            'items': [{
                'snippet': {
                    'title': 'Test Channel',
                    'thumbnails': {'default': {'url': 'http://example.com/icon.jpg'}}
                },
                'statistics': {'subscriberCount': '1000'}
            }]
        }
        mock_youtube.channels().list().execute.return_value = mock_response

        # Execution
        info = youtube_service.get_channel_info(1)

        # Verification
        self.assertEqual(info['name'], 'Test Channel')
        self.assertEqual(info['subscriber_count'], 1000)
        self.assertEqual(info['icon'], 'http://example.com/icon.jpg')

    @patch('youtube_service.get_youtube_client')
    @patch('youtube_service.get_analytics_client')
    def test_get_recent_videos(self, mock_get_analytics, mock_get_client):
        # Mock setup
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        
        # 1. Channels list response (Uploads playlist ID)
        mock_youtube.channels().list().execute.return_value = {
            'items': [{'contentDetails': {'relatedPlaylists': {'uploads': 'UU123'}}}]
        }
        
        # 2. Playlist items response
        mock_youtube.playlistItems().list().execute.return_value = {
            'items': [
                {
                    'contentDetails': {'videoId': 'vid1'},
                    'snippet': {
                        'title': 'Video 1',
                        'thumbnails': {'medium': {'url': 'http://example.com/v1.jpg'}},
                        'publishedAt': '2023-01-01T00:00:00Z'
                    }
                }
            ]
        }
        
        # 3. Videos list response (Statistics)
        mock_youtube.videos().list().execute.return_value = {
            'items': [
                {
                    'id': 'vid1',
                    'statistics': {'viewCount': '100'},
                    'contentDetails': {'duration': 'PT1M'}
                }
            ]
        }
        
        # 4. Analytics response
        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics
        mock_analytics.reports().query().execute.return_value = {
            'rows': [['vid1', 10, 60]] # vid, estimatedMinutesWatched, averageViewDuration
        }

        # Execution
        videos = youtube_service.get_recent_videos(1, limit=1)

        # Verification
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]['id'], 'vid1')
        self.assertEqual(videos[0]['view_count'], 100)
        self.assertEqual(videos[0]['watch_time_mins'], 10)

    @patch('youtube_service.get_youtube_client')
    @patch('youtube_service.database.get_user')
    def test_get_video_comments(self, mock_get_user, mock_get_client):
        # Mock setup
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_get_user.return_value = {'channel_id': 'MY_CHANNEL_ID'}
        
        mock_response = {
            'items': [
                {
                    'id': 'thread1',
                    'snippet': {
                        'topLevelComment': {
                            'id': 'comment1',
                            'snippet': {
                                'authorChannelId': {'value': 'OTHER_CHANNEL_ID'},
                                'textDisplay': 'Hello',
                                'authorDisplayName': 'User A',
                                'authorProfileImageUrl': 'http://example.com/a.jpg',
                                'publishedAt': '2023-01-01T00:00:00Z',
                                'likeCount': 5
                            }
                        }
                    }
                },
                {
                    'id': 'thread2',
                    'snippet': {
                        'topLevelComment': {
                            'id': 'comment2',
                            'snippet': {
                                'authorChannelId': {'value': 'OTHER_CHANNEL_ID'},
                                'textDisplay': 'Question',
                                'authorDisplayName': 'User B',
                                'authorProfileImageUrl': 'http://example.com/b.jpg',
                                'publishedAt': '2023-01-02T00:00:00Z'
                            }
                        }
                    },
                    'replies': {
                        'comments': [
                            {
                                'id': 'reply1',
                                'snippet': {
                                    'authorChannelId': {'value': 'MY_CHANNEL_ID'},
                                    'authorDisplayName': 'Me',
                                    'authorProfileImageUrl': 'http://example.com/me.jpg',
                                    'textDisplay': 'Answer',
                                    'publishedAt': '2023-01-02T01:00:00Z'
                                }
                            }
                        ]
                    }
                }
            ]
        }
        mock_youtube.commentThreads().list().execute.return_value = mock_response

        # Execution
        comments = youtube_service.get_video_comments(1, 'vid1')

        # Verification
        self.assertEqual(len(comments['unreplied']), 1)
        self.assertEqual(comments['unreplied'][0]['text'], 'Hello')
        
        self.assertEqual(len(comments['replied']), 1)
        self.assertEqual(comments['replied'][0]['text'], 'Question')
        self.assertEqual(len(comments['replied'][0]['replies']), 1)
        self.assertTrue(comments['replied'][0]['replies'][0]['is_mine'])

    @patch('youtube_service.get_youtube_client')
    def test_post_reply(self, mock_get_client):
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        
        youtube_service.post_reply(1, 'parent1', 'Thanks')
        
        mock_youtube.comments().insert.assert_called_with(
            part='snippet',
            body={
                'snippet': {
                    'parentId': 'parent1',
                    'textOriginal': 'Thanks'
                }
            }
        )

    @patch('youtube_service.get_youtube_client')
    def test_delete_comment(self, mock_get_client):
        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        
        youtube_service.delete_comment(1, 'comment1')
        
        mock_youtube.comments().delete.assert_called_with(id='comment1')

    @patch('youtube_service.auth.get_credentials_from_user')
    @patch('youtube_service.database.get_user')
    @patch('youtube_service.AuthorizedSession')
    def test_rate_comment(self, mock_auth_session_cls, mock_get_user, mock_get_creds):
        mock_session = MagicMock()
        mock_auth_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_session.post.return_value = mock_response
        
        youtube_service.rate_comment(1, 'comment1', 'like')
        
        mock_session.post.assert_called_with(
            'https://www.googleapis.com/youtube/v3/comments/setRating',
            params={'id': 'comment1', 'rating': 'like'}
        )

if __name__ == '__main__':
    unittest.main()
