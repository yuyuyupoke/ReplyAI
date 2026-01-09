# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Comment さくさく Checker (ReplyAI)** - A YouTube comment management tool that helps channel owners respond to comments efficiently using AI-powered reply suggestions. The goal is to help YouTubers improve engagement by making it easy to reply to comments with context-aware, personalized responses.

**Business Goal**: Achieve monthly revenue of ¥1,000,000.

## Development Commands

### Local Development

```bash
# Start the application (development mode)
python run.py

# Start with mock data (no Google API calls)
USE_MOCK_DATA=true python run.py

# Access at http://localhost:8080
```

### Production Deployment

```bash
# Production server (Render.com)
gunicorn app:app --bind 0.0.0.0:8080
```

### Using Ngrok (for external testing)

```bash
# Start app in background
venv/bin/python run.py &

# Expose via ngrok
ngrok http 8080

# Remember to add the ngrok URL to Google Cloud Console redirect URIs:
# https://xxxx.ngrok-free.dev/auth/callback
```

### Troubleshooting

```bash
# Kill process on port 8080
lsof -t -i :8080 | xargs kill -9

# Check ngrok status
curl -s http://localhost:4040/api/tunnels | grep public_url
```

## Architecture Overview

### Authentication Flow (Critical)

This app uses **Supabase Auth with Google OAuth** instead of traditional Google OAuth flow:

1. User clicks "Login with Google" → `login.html` calls `supabase.auth.signInWithOAuth()`
2. Google authentication with YouTube scopes (`youtube.force-ssl`, `yt-analytics.readonly`)
3. Redirect to `callback.html` which extracts session from URL hash fragment
4. Frontend POSTs to `/api/auth/session` with tokens (Supabase JWT + Google tokens)
5. Backend saves tokens to `user_tokens` table, fetches YouTube `channel_id`
6. Flask session stores `user_id`, user redirected to `/videos`

**Key Point**: The frontend handles OAuth callback via hash fragment, not query params. The `callback.html` template extracts tokens and sends them to the backend.

### Service Layer Architecture

The app uses a **service-oriented architecture** with conditional imports:

```python
# app/__init__.py determines which service to use
if USE_MOCK_DATA:
    from app.services import mock_youtube_service as youtube_service
else:
    from app.services import youtube_service
```

**Services**:
- `youtube_service.py` - All YouTube API operations (videos, comments, replies, analytics)
- `ai_service.py` - Gemini 2.5 Flash Lite integration for reply suggestions
- `auth.py` - Google OAuth credential management
- `mock_youtube_service.py` - Dev mode with fake data (no API calls)

### Database Layer (Supabase)

Uses **Supabase PostgreSQL** with Row Level Security (RLS). Tables:

- `user_tokens` - OAuth tokens, channel_id, JWT (one per user)
- `reply_logs` - Reply history for AI learning (stores original comment, AI suggestion, final reply, edit flag)
- `usage_logs` - Gemini API token usage tracking
- `thread_states` - Comment completion status ("保留" feature)

**Database Access Pattern**: Prefers `supabase_admin` (service role) to bypass RLS, falls back to JWT authentication if admin client unavailable.

### AI Reply Generation Flow

1. User clicks "✨ 返信案を生成" on a comment
2. Frontend calls `/generate_reply` with `comment_text` and `video_id`
3. Backend fetches video context (title, description) and **few-shot examples** from `reply_logs`
4. `ai_service.generate_reply_suggestions()` builds prompt with:
   - Role: YouTube channel operator
   - Video context
   - **Few-shot learning**: Last 3 user-edited replies (to mimic user's tone)
   - Safety guidelines (no finance advice, hate speech, external links, sub4sub, personal info)
   - Task: Generate 3 reply patterns (empathy/gratitude, question/engagement, short/witty)
5. Gemini API returns 3 suggestions as bullet points
6. Usage logged to `usage_logs` (input/output tokens)
7. Frontend displays suggestions as clickable chips

**Critical**: The AI learns from `reply_logs` where `is_edited=true`, meaning it copies the user's writing style over time.

### Comment Classification System

Comments are categorized into 3 states:
- **未返信 (Unreplied)** - No reply from channel owner
- **保留 (On Hold)** - Marked complete without reply (in `thread_states`)
- **返信済み (Replied)** - Has reply from channel owner

This classification happens in `youtube_service.get_video_comments()` by checking:
1. If comment has replies from channel owner → "返信済み"
2. If comment_id exists in `thread_states` → "保留"
3. Otherwise → "未返信"

## Development Workflow (Important)

Per `documents/development_policy.md`:

1. **Always develop in Dev mode first** (`USE_MOCK_DATA=true`)
   - Implement features using `mock_youtube_service.py`
   - No Google API quota consumed
   - Fast iteration

2. **Get user approval** before touching production
   - Show screenshots or logs of working feature in dev mode
   - Use Antigravity Browser Extension to test all buttons

3. **Deploy to production** only after approval
   - Set `USE_MOCK_DATA=false`
   - Do smoke testing (minimize API usage)

## API References

When implementing YouTube API features, **always** reference:
https://developers.google.com/youtube/v3/docs

Key APIs used:
- `channels().list()` - Channel info (name, subscriber count, icon)
- `playlistItems().list()` - Video list from uploads playlist
- `videos().list()` - Video statistics (views)
- `youtubeAnalytics.reports().query()` - Watch time data
- `commentThreads().list()` - Fetch comments (with pagination)
- `comments().insert()` - Post replies
- `comments().delete()` - Delete comments

## Environment Variables

Required in `.env`:

```bash
SECRET_KEY                    # Flask session secret
CLIENT_SECRET_FILE            # Path to Google OAuth client_secret.json
GEMINI_API_KEY                # Google Gemini API key
SUPABASE_URL                  # Supabase project URL
SUPABASE_KEY                  # Supabase anon key
SUPABASE_SERVICE_KEY          # Supabase service role key (admin operations)
USE_MOCK_DATA                 # "true" for dev mode, "false" for production
OAUTHLIB_INSECURE_TRANSPORT   # "1" for development (allows HTTP)
```

See `.env.example` for template.

## Key Implementation Patterns

### Route Protection

All authenticated routes follow this pattern:

```python
@app.route('/some-route')
def some_route():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if not database.get_user(session['user_id']):
        session.clear()
        return redirect(url_for('index'))

    # ... route logic
```

### YouTube API Quota Optimization

- Batch fetch videos (50 at a time with `playlistItems.list`)
- Use `max_pages` parameter in `get_video_comments()` to limit API calls
- `/videos` page only fetches stats for current page (50 videos), not all 200

### Few-Shot Learning

The AI improves over time by learning from user edits:

```python
# In database.py
def get_few_shot_examples(user_id, limit=3):
    # Prioritizes is_edited=true (user customized the AI suggestion)
    # Returns last 3 examples with original_comment → final_reply
```

### Error Handling for Token Expiry

```python
try:
    # YouTube API call
except RefreshError:
    session.clear()
    return redirect(url_for('login'))
```

## Special Considerations

### Frontend-Backend Token Flow

Unlike typical OAuth, this app has **frontend-initiated OAuth** (Supabase) with backend token storage:
- Frontend gets Supabase session from URL hash
- Frontend extracts `access_token` (Supabase JWT), `provider_token` (Google), `provider_refresh_token`
- Frontend POSTs these to `/api/auth/session`
- Backend stores in database and sets Flask session

Do not try to initiate OAuth from Flask's `redirect()` - it won't work with Supabase's flow.

### Mock Service Parity

When modifying `youtube_service.py`, ensure `mock_youtube_service.py` has equivalent function signatures. The mock should:
- Return same data structure
- Simulate realistic edge cases
- Not make external API calls

### AI Prompt Engineering

The AI prompt in `ai_service.py` is critical to quality. When modifying:
- Keep few-shot examples at top of prompt (high attention)
- Maintain safety guidelines (prevents problematic replies)
- Ensure bullet-point output format (`-` prefix) for parsing
- Video description truncated to 300 chars (cost optimization)

## Project Structure Highlights

```
app/
├── __init__.py           # App initialization, USE_MOCK_DATA flag
├── routes.py             # All Flask routes
├── database.py           # Supabase operations
├── services/
│   ├── youtube_service.py      # Real YouTube API
│   ├── mock_youtube_service.py # Dev mode
│   ├── ai_service.py           # Gemini API
│   └── auth.py                 # OAuth helpers
├── utils/
│   └── supabase_client.py      # Supabase client init
└── templates/
    ├── login.html              # Supabase OAuth initiation
    ├── callback.html           # OAuth callback handler (hash fragment)
    ├── videos.html             # Video list
    ├── comments.html           # Comment list
    └── comment_card_v2.html    # Individual comment UI
```

## Testing Philosophy

From `development_policy.md`:
> 実装したら、全てのボタンが正常に動作するのかを、Antigravity Browser Extensionを利用して 必ず確認する

After implementation, **always test all buttons** using Antigravity Browser Extension to ensure full functionality.

## Important Notes for COO/CTO Modes

This project has custom agent rules in `.agent/rules/direction-style.md`:
- **COO Mode**: Focus on business strategy, operations, marketing toward ¥1M/month goal
- **CTO Mode**: Full-stack technical decisions, prioritize features by business impact
- Both modes: Be logical, challenge assumptions, propose alternatives, no "yes-man" behavior
- All conversations should be saved as meeting notes in `documents/` folder

When working on this codebase, remember:
- Every feature decision should tie back to the business goal
- Evaluate features by: Impact × Feasibility × Scalability
- Technical quality matters - own the implementation, ensure no errors before reporting
