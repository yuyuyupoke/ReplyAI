async function generateReply(commentId, videoId, commentText) {
    const btn = document.querySelector(`#comment-${commentId} .btn-generate`);
    const suggestionsBox = document.getElementById(`suggestions-${commentId}`);

    // Custom prompt is removed from UI, so we send null or empty
    let customInstruction = null;
    // If we had a hidden field for it, we could use it, but for now it's gone.

    // Determine which button is active
    const regenBtn = document.getElementById(`btn-regenerate-${commentId}`);
    let activeBtn = btn;
    if (regenBtn && regenBtn.style.display !== 'none') {
        activeBtn = regenBtn;
    }

    activeBtn.disabled = true;
    const originalText = activeBtn.textContent;
    activeBtn.textContent = "生成中... 🤖";

    try {
        const response = await fetch('/generate_reply', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                comment_text: commentText,
                video_id: videoId,
                custom_instruction: customInstruction
            }),
        });

        const data = await response.json();

        if (data.status === 'error') {
            throw new Error(data.message);
        }

        if (!data.suggestions || !Array.isArray(data.suggestions)) {
            throw new Error("Invalid response from server");
        }

        suggestionsBox.innerHTML = '';
        data.suggestions.forEach((suggestion, index) => {
            const chip = document.createElement('div');
            chip.className = 'suggestion-chip';
            chip.textContent = suggestion;
            chip.onclick = () => selectSuggestion(commentId, suggestion);

            if (index === 0) {
                document.getElementById(`ai-suggestion-${commentId}`).value = suggestion;
            }

            suggestionsBox.appendChild(chip);
        });

        suggestionsBox.style.display = 'flex';
        document.getElementById(`reply-text-${commentId}`).style.display = 'block';
        document.getElementById(`btn-post-${commentId}`).style.display = 'block';

        // Switch buttons
        btn.style.display = 'none';
        if (regenBtn) {
            regenBtn.style.display = 'inline-block';
            regenBtn.disabled = false;
            regenBtn.textContent = "🔄 再生成";
        }


    } catch (error) {
        alert('生成に失敗しました: ' + error);
        activeBtn.disabled = false;
        activeBtn.textContent = originalText;
    }
}

function selectSuggestion(commentId, text) {
    const textarea = document.getElementById(`reply-text-${commentId}`);
    textarea.value = text;
    document.getElementById(`ai-suggestion-${commentId}`).value = text;
}

async function postReply(commentId, isReplied = false, videoId = '') {
    const textarea = document.getElementById(`reply-text-${commentId}`);
    const text = textarea.value;
    const btn = document.getElementById(`btn-post-${commentId}`);

    const originalComment = document.getElementById(`original-comment-${commentId}`).value;
    const aiSuggestion = document.getElementById(`ai-suggestion-${commentId}`).value;

    if (!text) return;

    btn.disabled = true;
    btn.textContent = "投稿中...";

    try {
        const response = await fetch('/post_reply', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                parent_id: commentId,
                reply_text: text,
                original_comment: originalComment,
                ai_suggestion: aiSuggestion,
                video_id: videoId
            }),
        });

        const data = await response.json();

        if (data.status === 'success') {
            console.log('New reply ID:', data.id);
            const card = document.getElementById(`comment-${commentId}`);

            // Create reply thread container if it doesn't exist
            let thread = document.getElementById(`thread-${commentId}`);
            if (!thread) {
                thread = document.createElement('div');
                thread.className = 'reply-thread';
                thread.id = `thread-${commentId}`;
                // Insert after comment-text
                const commentTextDiv = card.querySelector('.comment-text');
                commentTextDiv.parentNode.insertBefore(thread, commentTextDiv.nextSibling);
            }

            // Create new reply item
            const newReply = document.createElement('div');
            newReply.className = 'reply-item my-reply';
            newReply.id = `comment-${data.id}`;
            newReply.innerHTML = `
                <img src="${data.author_image || '/static/default-avatar.png'}" alt="${data.author_name || 'You'}" class="reply-author-img">
                <div class="reply-content">
                    <div class="reply-header">
                        <span class="reply-author-name">@${data.author_name || 'You'}</span>
                        <span class="reply-date">${data.published_at ? data.published_at.substring(0, 10) : new Date().toISOString().split('T')[0]}</span>
                        <button class="btn-icon-small" onclick="deleteComment('${data.id}')" title="削除">🗑️</button>
                    </div>
                    <div class="reply-text">${text}</div>
                </div>
            `;
            thread.appendChild(newReply);

            // If it was unreplied, mark it as replied and move it
            if (!isReplied) {
                card.classList.add('replied-comment-card');

                // Move to bottom of the list
                const list = document.getElementById('comments-list');
                list.appendChild(card);

                // Update button onclick to treat it as replied next time
                btn.setAttribute('onclick', `postReply('${commentId}', true, '${videoId}')`);
            }

            // Reset the form
            textarea.value = '';
            // Don't hide textarea, keep it visible as per new design
            // textarea.style.display = 'none'; 
            // btn.style.display = 'none';

            // Just clear suggestions
            const suggestionsBox = document.getElementById(`suggestions-${commentId}`);
            if (suggestionsBox) suggestionsBox.style.display = 'none';

            // Reset generate button
            const genBtn = document.getElementById(`btn-generate-${commentId}`);
            const regenBtn = document.getElementById(`btn-regenerate-${commentId}`);
            if (genBtn) genBtn.style.display = 'inline-block';
            if (regenBtn) regenBtn.style.display = 'none';

            btn.disabled = false;
            btn.textContent = "返信を投稿";

            // Update Reply Rate Widget
            const widget = document.querySelector('.reply-stats-widget');
            if (widget && !isReplied) {
                const unrepliedCountSpan = widget.querySelector('.unreplied-count');
                const repliedCountSpan = widget.querySelector('.replied-count');
                const rateValueSpan = widget.querySelector('.rate-value');

                if (unrepliedCountSpan && repliedCountSpan && rateValueSpan) {
                    let unreplied = parseInt(unrepliedCountSpan.textContent.replace(/,/g, ''));
                    let replied = parseInt(repliedCountSpan.textContent.replace(/,/g, ''));

                    if (!isNaN(unreplied) && !isNaN(replied)) {
                        unreplied = Math.max(0, unreplied - 1);
                        replied++;

                        unrepliedCountSpan.textContent = unreplied;
                        repliedCountSpan.textContent = replied;

                        const total = unreplied + replied;
                        let rate = 0;
                        if (total > 0) {
                            rate = Math.floor((replied / total) * 100);
                        }
                        // Widget shows Unreplied Rate (100 - rate)
                        rateValueSpan.textContent = (100 - rate) + '%';
                    }
                }
            }

        } else {
            alert('投稿失敗: ' + data.message);
            btn.disabled = false;
            btn.textContent = "返信を投稿";
        }

    } catch (error) {
        alert('エラーが発生しました: ' + error);
        btn.disabled = false;
        btn.textContent = "返信を投稿";
    }
}
function toggleSection(id, header) {
    const list = document.getElementById(id);
    if (list.style.display === 'none') {
        list.style.display = 'block';
        header.textContent = header.textContent.replace('▶', '▼');
    } else {
        list.style.display = 'none';
        header.textContent = header.textContent.replace('▼', '▶');
    }
}

function togglePrompt(commentId) {
    const box = document.getElementById(`prompt-box-${commentId}`);
    if (box.style.display === 'none') {
        box.style.display = 'block';
    } else {
        box.style.display = 'none';
    }
}

async function deleteComment(commentId) {
    if (!confirm('本当にこのコメントを削除しますか？取り消し不可能です。')) return;

    console.log('Attempting to delete comment with ID:', commentId);
    const elementId = 'comment-' + commentId;
    const element = document.getElementById(elementId);
    console.log('Element found:', element);

    if (!element) {
        alert('エラー: 削除対象の要素が見つかりませんでした (ID: ' + elementId + ')');
        return;
    }

    try {
        const response = await fetch('/delete_comment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ comment_id: commentId }),
        });

        const data = await response.json();
        if (data.status === 'success') {
            if (element) {
                console.log('Removing element from DOM:', element);
                element.style.display = 'none'; // Force hide first
                element.remove(); // Then remove
                console.log('Element removed.');
            } else {
                console.warn('Element not found in DOM, but deleted from server.');
                location.reload();
            }
        } else {
            alert('削除に失敗しました: ' + (data.message || '不明なエラー'));
        }
    } catch (error) {
        alert('エラーが発生しました: ' + error);
    }
}

// rateComment function removed due to API limitations
