from googleapiclient.discovery import build
import os

# We don't need real creds to check the resource structure, 
# but build might need a key or just work for discovery.
# We'll try without args first, or with a dummy key if needed.
try:
    youtube = build('youtube', 'v3', developerKey='DUMMY')
    print("Successfully built youtube service")
    if hasattr(youtube, 'comments'):
        comments = youtube.comments()
        print(f"Attributes of youtube.comments(): {dir(comments)}")
        if 'setRating' in dir(comments):
            print("setRating method FOUND")
        else:
            print("setRating method NOT FOUND")
    else:
        print("comments resource NOT FOUND")
except Exception as e:
    print(f"Error building service: {e}")
