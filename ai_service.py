import os
from google import genai
from google.genai import types

def generate_reply_suggestions(comment_text, custom_instruction=None, examples=None):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return ["Error: GEMINI_API_KEY not set."], None

    client = genai.Client(api_key=api_key)
    
    instruction_text = custom_instruction if custom_instruction else "フレンドリーで親しみやすい口調で、必ず最後に感謝の意を簡潔に示し、絵文字を1つ付けてください。"

    # Construct Few-Shot Examples
    examples_text = ""
    if examples:
        examples_text = "\n    【あなたの過去の返信スタイル（参考）】\n"
        for i, ex in enumerate(examples, 1):
            examples_text += f"    例{i}:\n    視聴者: {ex['comment']}\n    あなた: {ex['reply']}\n\n"
        examples_text += "    これらの過去の返信の「口調」「長さ」「絵文字の使い方」を強く意識して真似てください。\n"

    prompt = f"""
    役割: あなたはYouTubeチャンネルの運営者です。
    
    {examples_text}
    
    【重要：安全ガイドライン】
    以下のトピックに関する返信は絶対に生成しないでください。もしコメントがこれらに該当する場合は、無難な挨拶のみ、または返信しないことを提案してください。
    1. 金融・投資アドバイス（仮想通貨、株など）
    2. 暴力、ヘイトスピーチ、差別的表現
    3. 外部サイトへの誘導、URLの記載
    4. 「チャンネル登録して」などの相互登録依頼（Sub4Sub）
    5. 個人情報の聞き出し

    コメント本文: 視聴者からのコメント「{comment_text}」
    
    指示: 以下の指示に従い、返信を3パターン提案してください。各提案は箇条書き（- ）で記載し、それ以外の説明や前置きは一切不要です。
    指示：{instruction_text}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp', # Or gemini-1.5-flash
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
            )
        )
        
        text = response.text
        # Parse bullet points
        suggestions = [line.strip('- ').strip() for line in text.split('\n') if line.strip().startswith('-')]
        
        # Fallback if parsing fails but text exists
        if not suggestions and text:
            suggestions = [text]
            
        usage = {
            'input_tokens': response.usage_metadata.prompt_token_count,
            'output_tokens': response.usage_metadata.candidates_token_count,
            'model_name': 'gemini-2.0-flash-exp'
        }
            
        return suggestions[:3], usage
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return [f"Error generating reply: {str(e)}"], None
