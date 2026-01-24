// Bulk Operations for Comment Management

function updateBulkBar() {
    const checkboxes = document.querySelectorAll('.comment-checkbox:checked');
    const count = checkboxes.length;
    const bar = document.getElementById('bulk-bar');
    const countEl = document.getElementById('bulk-count');

    if (count > 0) {
        bar.style.display = 'flex';
        countEl.textContent = `${count}件選択中`;
    } else {
        bar.style.display = 'none';
    }
}

function getSelectedComments() {
    const checkboxes = document.querySelectorAll('.comment-checkbox:checked');
    const selected = [];

    checkboxes.forEach(checkbox => {
        selected.push({
            id: checkbox.dataset.commentId,
            videoId: checkbox.dataset.videoId,
            text: checkbox.dataset.commentText
        });
    });

    return selected;
}

async function bulkGenerate() {
    const selected = getSelectedComments();
    if (selected.length === 0) {
        alert('コメントを選択してください');
        return;
    }

    if (!confirm(`${selected.length}件のコメントに対して返信を生成します。よろしいですか？`)) {
        return;
    }

    // Show progress modal
    const modal = showProgressModal(selected.length, '返信生成中');

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < selected.length; i++) {
        const comment = selected[i];

        try {
            await generateReply(comment.id, comment.videoId, comment.text);
            successCount++;
        } catch (error) {
            console.error(`Failed to generate reply for comment ${comment.id}:`, error);
            failCount++;
        }

        modal.update(i + 1, successCount, failCount);

        // Wait 500ms to avoid API rate limits
        if (i < selected.length - 1) {
            await sleep(500);
        }
    }

    modal.close();
    clearSelection();

    // Show summary
    alert(`一括返信生成が完了しました。\n成功: ${successCount}件\n失敗: ${failCount}件`);
}

async function bulkMarkComplete() {
    const selected = getSelectedComments();
    if (selected.length === 0) {
        alert('コメントを選択してください');
        return;
    }

    if (!confirm(`${selected.length}件のコメントを保留にします。よろしいですか？`)) {
        return;
    }

    // Show progress modal
    const modal = showProgressModal(selected.length, '保留処理中');

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < selected.length; i++) {
        const comment = selected[i];

        try {
            await markComplete(comment.id);
            successCount++;
        } catch (error) {
            console.error(`Failed to mark complete for comment ${comment.id}:`, error);
            failCount++;
        }

        modal.update(i + 1, successCount, failCount);

        // Wait 200ms between operations
        if (i < selected.length - 1) {
            await sleep(200);
        }
    }

    modal.close();
    clearSelection();

    // Show summary
    alert(`一括保留が完了しました。\n成功: ${successCount}件\n失敗: ${failCount}件`);
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('.comment-checkbox:checked');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    updateBulkBar();
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function showProgressModal(total, title = '処理中') {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'progress-modal';

    // Create modal content
    const modal = document.createElement('div');
    modal.className = 'modal-content';
    modal.innerHTML = `
        <h3>${title}</h3>
        <div class="progress-bar-container">
            <div class="progress-bar" id="progress-bar" style="width: 0%;"></div>
        </div>
        <p id="progress-text">0 / ${total} 完了 (成功: 0, 失敗: 0)</p>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    return {
        update: function(current, successCount = 0, failCount = 0) {
            const percentage = (current / total) * 100;
            document.getElementById('progress-bar').style.width = percentage + '%';
            document.getElementById('progress-text').textContent =
                `${current} / ${total} 完了 (成功: ${successCount}, 失敗: ${failCount})`;
        },
        close: function() {
            const modal = document.getElementById('progress-modal');
            if (modal) {
                modal.remove();
            }
        }
    };
}

// Initialize event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Listen to checkbox changes
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('comment-checkbox')) {
            updateBulkBar();
        }
    });
});
