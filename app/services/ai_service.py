import os
from google import genai
from google.genai import types

def generate_reply_suggestions(comment_text, custom_instruction=None, examples=None):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return ["Error: GEMINI_API_KEY not set."], None

    client = genai.Client(api_key=api_key)
    
    instruction_text = custom_instruction if custom_instruction else "フレンドリーで親しみやすい口調で、必ず最後に感謝の意を簡潔に示し、絵文字を1つ付けてください。"

    # Construct Few-Shot Examples with Strong Instruction
    examples_text = ""
    if examples:
        examples_text = "\n    【学習データ（あなたの口調の正解データ）】\n"
        examples_text += "    以下の過去のやり取りにおける「あなたの返信」の文体、絵文字の選び方、文の長さを**徹底的に模倣**してください。\n"
        examples_text += "    内容は今回のコメントに合わせて変えますが、**「話し方の癖」はこれらを完全にコピー**してください。\n\n"
        for i, ex in enumerate(examples, 1):
            examples_text += f"    データ{i}:\n    視聴者: {ex['comment']}\n    あなた: {ex['reply']}\n\n"
    else:
        examples_text = "    (学習データなし: 一般的な親しみやすいYouTuberとして振る舞ってください)\n"

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

    【今回のタスク】
    以下の視聴者コメントに対して、学習したスタイル（口調）を維持したまま、アプローチの異なる3つの返信を生成してください。

    視聴者コメント: 「{comment_text}」
    
    【生成する3つのパターン】
    1. **共感・感謝型**: 相手のコメントに深く共感し、感謝を伝える（最も丁寧で安全なパターン）。
    2. **質問・交流型**: 会話を続けるために、関連する質問を投げかける（エンゲージメントを高めるパターン）。
    3. **短文・ウィット型**: 短く、気の利いた一言やリアクションで返す（親近感を演出するパターン）。

    【制約事項】
    - 出力は箇条書き（- ）で3行のみ出力してください。
    - 各行は「パターン名」を含まず、返信本文のみを記述してください。
    - 前置きや解説は一切不要です。
    - 追加指示：{instruction_text}
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
