import database
import ai_service
import os

# Mock user ID for testing
USER_ID = 1

def test_feedback_loop():
    print("=== Testing Feedback Loop ===")
    
    # 1. Simulate logging a reply with an edit
    print("\n1. Logging a manual correction...")
    original_comment = "面白い動画でした！"
    ai_suggestion = "ありがとうございます！嬉しいです！😊"
    final_reply = "ありがとうございます！次も頑張ります！🔥" # Edited
    
    database.log_reply(
        user_id=USER_ID,
        video_id="test_vid",
        comment_id="test_comment_1",
        original_comment=original_comment,
        ai_suggestion=ai_suggestion,
        final_reply=final_reply
    )
    print("Logged reply.")

    # 2. Verify it's retrieved as an example
    print("\n2. Verifying retrieval...")
    examples = database.get_few_shot_examples(USER_ID)
    if examples and examples[0]['reply'] == final_reply:
        print("✅ Success: Edited reply retrieved as example.")
    else:
        print("❌ Failed: Edited reply not found in examples.")
        print(f"Examples found: {examples}")

    # 3. Generate new reply using examples
    print("\n3. Generating new reply with examples...")
    new_comment = "参考になりました！"
    
    # Mock API key if not present (for dry run logic check)
    if not os.environ.get('GEMINI_API_KEY'):
        print("⚠️ GEMINI_API_KEY not set. Skipping actual API call.")
        return

    suggestions, _ = ai_service.generate_reply_suggestions(new_comment, examples=examples)
    
    print(f"Input Comment: {new_comment}")
    print("Suggestions:")
    for s in suggestions:
        print(f"- {s}")
        
    print("\nCheck if the style matches the edited reply (e.g. use of 🔥 or similar tone).")

if __name__ == "__main__":
    # Ensure DB is init
    database.init_db()
    test_feedback_loop()
