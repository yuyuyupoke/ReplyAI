import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class TestApp(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.secret_key = 'test_secret'
        self.client = app.test_client()

    def test_index_redirect(self):
        # No session -> login page
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Google', response.data)

        # With session -> videos
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/videos', response.headers['Location'])

    @patch('app.database.get_user')
    @patch('app.services.youtube_service.get_recent_videos')
    @patch('app.services.youtube_service.get_channel_info')
    def test_videos_route(self, mock_get_info, mock_get_videos, mock_get_user):
        mock_get_user.return_value = {'id': 1}
        mock_get_videos.return_value = []
        mock_get_info.return_value = {'name': 'Test Channel', 'icon': 'icon.jpg', 'subscriber_count': 100}
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            
        response = self.client.get('/videos')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Channel', response.data)

    @patch('app.database.get_user')
    @patch('app.services.youtube_service.get_video_details')
    @patch('app.services.youtube_service.get_video_comments')
    def test_comments_route(self, mock_get_comments, mock_get_details, mock_get_user):
        mock_get_user.return_value = {'id': 1}
        mock_get_comments.return_value = {'comments': [], 'stats': {'total': 0, 'replied': 0, 'unreplied': 0, 'rate': 0}}
        mock_get_details.return_value = {'id': 'vid1', 'title': 'Test Video', 'thumbnail': 'thumb.jpg'}
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            
        response = self.client.get('/comments/vid1')
        self.assertEqual(response.status_code, 200)

    @patch('app.database.get_user')
    @patch('app.services.youtube_service.post_reply')
    def test_post_reply_api(self, mock_post_reply, mock_get_user):
        mock_get_user.return_value = {'id': 1}
        mock_post_reply.return_value = {
            'id': 'reply1',
            'snippet': {
                'authorProfileImageUrl': 'http://example.com/me.jpg',
                'authorDisplayName': 'Me',
                'publishedAt': '2023-01-01T00:00:00Z'
            }
        }
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            
        response = self.client.post('/post_reply', 
                                  json={'parent_id': 'p1', 'reply_text': 'test'},
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'success')
        mock_post_reply.assert_called_with(1, 'p1', 'test')

    @patch('app.database.get_user')
    @patch('app.services.youtube_service.delete_comment')
    def test_delete_comment_api(self, mock_delete, mock_get_user):
        mock_get_user.return_value = {'id': 1}
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            
        response = self.client.post('/delete_comment', 
                                  json={'comment_id': 'c1'},
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'success')
        mock_delete.assert_called_with(1, 'c1')

    @patch('app.database.get_user')
    @patch('app.services.youtube_service.rate_comment')
    def test_rate_comment_api(self, mock_rate, mock_get_user):
        mock_get_user.return_value = {'id': 1}
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            
        response = self.client.post('/rate_comment', 
                                  json={'comment_id': 'c1', 'rating': 'like'},
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'success')
        mock_rate.assert_called_with(1, 'c1', 'like')

    def test_generate_reply_api(self):
        with patch('app.database.get_user') as mock_get_user, \
             patch('app.routes.ai_service.generate_reply_suggestions') as mock_generate, \
             patch('app.database.log_usage') as mock_log:
            
            mock_get_user.return_value = {'id': 1}
            mock_generate.return_value = (['Suggestion 1'], {'input_tokens': 10, 'output_tokens': 10, 'model_name': 'test'})
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = 1
                
            response = self.client.post('/generate_reply', 
                                      json={'comment': 'Hello', 'instruction': 'Friendly'},
                                      content_type='application/json')
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['suggestions'][0], 'Suggestion 1')

if __name__ == '__main__':
    unittest.main()
