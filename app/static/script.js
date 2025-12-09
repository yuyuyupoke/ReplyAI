async function generateReply(commentId, videoId, commentText) {
    const btn = document.querySelector(`#comment-${commentId} .btn-generate`);
    const suggestionsBox = document.getElementById(`suggestions-${commentId}`);



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
                custom_instruction: null
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
            // Update Reply Rate Widget with Animation
            // Unreplied -1, Pending 0, Replied +1
            updateStatsUI(-1, 0, 1);

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

    // Check if this is a reply item (not a proper comment card)
    const isReplyItem = element.classList.contains('reply-item');
    const card = element.closest('.comment-card');
    const threadContainer = element.parentElement; // .reply-thread

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

                // Logic: If this was the last 'my-reply' in the thread, revert to Unreplied.
                if (isReplyItem && card) {
                    // Check if there are any other replies BY ME left
                    // We look for .reply-item.my-reply inside the same thread container
                    const remainingReplies = threadContainer.querySelectorAll('.reply-item.my-reply');

                    if (remainingReplies.length === 0) {
                        // Revert status to Unreplied
                        if (card.classList.contains('replied-comment-card')) {
                            card.classList.remove('replied-comment-card');

                            // Update Stats Widget: Replied -1, Unreplied +1
                            updateStatsUI(1, 0, -1);

                            // Update the "Post Reply" button to reflect isReplied = false
                            // Find the post button for this card
                            const btnPost = card.querySelector('.btn-post');
                            if (btnPost) {
                                // Extract videoId from existing onclick or assume it from context? 
                                // Hard to parse videoId efficiently from onclick string. 
                                // But postReply logic itself updates stats if !isReplied. 
                                // So setting it to false allows the NEXT reply to increment stats again correctly.
                                // We need to update the onclick attribute string.
                                // Current: postReply('id', true, 'vid')
                                // New:     postReply('id', false, 'vid')
                                const currentOnclick = btnPost.getAttribute('onclick');
                                const newOnclick = currentOnclick.replace('true', 'false');
                                btnPost.setAttribute('onclick', newOnclick);
                            }
                        }
                    }
                }

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

async function markComplete(commentId) {
    const btn = document.querySelector(`#comment-${commentId} .btn-icon[title="既読にする（保留）"]`);
    if (btn) btn.disabled = true;

    try {
        const response = await fetch('/mark_complete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ comment_id: commentId }),
        });

        const data = await response.json();
        if (data.status === 'success') {
            // Optimistic UI Update - No Reload

            // 1. Update Buttons
            // Hide "Mark Complete", Show "Unmark"
            // Since "Unmark" button might not exist if it wasn't pending, we might need to recreate it or toggle visibility if both exist.
            // Looking at template: It uses {% if %} so only one exists in DOM. We need to replace the button.

            const metaRight = document.getElementById(`meta-${commentId}`);
            if (metaRight) {
                // Remove the "Mark Complete" button
                if (btn) btn.remove();

                // Add the "Unmark" button
                // Check if it already exists (unlikely in this flow but just in case)
                let unmarkBtn = metaRight.querySelector('.btn-icon[title="既読を取り消す"]');
                if (!unmarkBtn) {
                    unmarkBtn = document.createElement('button');
                    unmarkBtn.className = 'btn-icon';
                    unmarkBtn.onclick = () => unmarkComplete(commentId);
                    unmarkBtn.title = "既読を取り消す";
                    unmarkBtn.innerHTML = '<span class="icon-emoji">↩️</span>';

                    // Insert before the delete button (last child usually)
                    const deleteBtn = metaRight.querySelector('.btn-icon[title="削除"]');
                    if (deleteBtn) {
                        metaRight.insertBefore(unmarkBtn, deleteBtn);
                    } else {
                        metaRight.appendChild(unmarkBtn);
                    }
                }
            }

            // Update Stats (Unreplied -1, Pending +1)
            updateStatsUI(-1, 1, 0);

            // 3. Update Card Style
            const card = document.getElementById(`comment-${commentId}`);
            if (card) {
                card.classList.add('pending-comment-card');
            }

        } else {
            alert('完了マークに失敗しました: ' + (data.message || '不明なエラー'));
            if (btn) btn.disabled = false;
        }
    } catch (error) {
        alert('エラーが発生しました: ' + error);
        if (btn) btn.disabled = false;
    }
}

async function unmarkComplete(commentId) {
    const btn = document.querySelector(`#comment-${commentId} .btn-icon[title="既読を取り消す"]`);
    if (btn) btn.disabled = true;

    try {
        const response = await fetch('/unmark_complete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ comment_id: commentId }),
        });

        const data = await response.json();
        if (data.status === 'success') {
            // Optimistic UI Update - No Reload

            // 1. Update Buttons
            const metaRight = document.getElementById(`meta-${commentId}`);
            if (metaRight) {
                // Remove "Unmark" button
                if (btn) btn.remove();

                // Add "Mark Complete" button
                let markBtn = metaRight.querySelector('.btn-icon[title="既読にする（保留）"]');
                if (!markBtn) {
                    markBtn = document.createElement('button');
                    markBtn.className = 'btn-icon';
                    markBtn.onclick = () => markComplete(commentId);
                    markBtn.title = "既読にする（保留）";
                    markBtn.innerHTML = '<span class="icon-emoji">✅</span>';

                    // Insert before delete button
                    const deleteBtn = metaRight.querySelector('.btn-icon[title="削除"]');
                    if (deleteBtn) {
                        metaRight.insertBefore(markBtn, deleteBtn);
                    } else {
                        metaRight.appendChild(markBtn);
                    }
                }
            }

            // Update Stats (Unreplied +1, Pending -1)
            updateStatsUI(1, -1, 0);

            // 3. Update Card Style
            const card = document.getElementById(`comment-${commentId}`);
            if (card) {
                card.classList.remove('pending-comment-card');
            }

        } else {
            alert('既読取り消しに失敗しました: ' + (data.message || '不明なエラー'));
            if (btn) btn.disabled = false;
        }
    } catch (error) {
        alert('エラーが発生しました: ' + error);
        if (btn) btn.disabled = false;
    }
}

// Simplified Stats Update Logic (No Animation, High Reliability)
function updateStatsUI(unrepliedChange, pendingChange, repliedChange) {
    const widget = document.querySelector('.stats-widget');
    if (!widget) return;

    const unrepliedEl = widget.querySelector('.stat-item.unreplied .stat-count');
    const pendingEl = widget.querySelector('.stat-item.pending .stat-count');
    const repliedEl = widget.querySelector('.stat-item.replied .stat-count');

    if (unrepliedEl) {
        let current = parseInt(unrepliedEl.textContent);
        if (!isNaN(current)) {
            unrepliedEl.textContent = Math.max(0, current + unrepliedChange);
        }
    }

    if (pendingEl) {
        let current = parseInt(pendingEl.textContent);
        if (!isNaN(current)) {
            pendingEl.textContent = Math.max(0, current + pendingChange);
        }
    }

    if (repliedEl) {
        let current = parseInt(repliedEl.textContent);
        if (!isNaN(current)) {
            repliedEl.textContent = Math.max(0, current + repliedChange);
        }
    }
}
