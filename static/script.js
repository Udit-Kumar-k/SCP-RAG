document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('searchForm');
    const loader = document.getElementById('loader');
    const resultsContainer = document.getElementById('resultsContainer');
    const welcomeMessage = document.getElementById('welcomeMessage');
    const scpCardsLayout = document.getElementById('scpCards');
    const aiResponseHtml = document.getElementById('aiResponse');
    const resultCountBadge = document.getElementById('resultCount');

    // ── Modal elements ──────────────────────────────────────────────────────
    const modal         = document.getElementById('scpModal');
    const modalScpId    = document.getElementById('modalScpId');
    const modalClass    = document.getElementById('modalClass');
    const modalText     = document.getElementById('modalText');
    const modalWikiLink = document.getElementById('modalWikiLink');
    const modalClose    = document.getElementById('modalClose');

    function openModal(scp) {
        const rawId = scp.scp_id.toString().toLowerCase().replace('scp-', '').trim();

        modalScpId.textContent  = scp.scp_id;
        modalClass.textContent  = scp.object_class;
        modalClass.className    = 'object-class';
        const objClass = scp.object_class.toLowerCase();
        if (objClass.includes('safe'))   modalClass.classList.add('class-safe');
        else if (objClass.includes('euclid')) modalClass.classList.add('class-euclid');
        else if (objClass.includes('keter'))  modalClass.classList.add('class-keter');

        modalWikiLink.href = `https://scp-wiki.wikidot.com/scp-${rawId}`;
        // Format the raw text a bit nicer — preserve line breaks
        modalText.innerHTML = scp.text
            .replace(/\[Containment Procedures\]/g, '<strong>[Containment Procedures]</strong>')
            .replace(/\[Description\]/g, '<strong>[Description]</strong>')
            .replace(/\[Addenda\]/g, '<strong>[Addenda]</strong>')
            .replace(/\n/g, '<br>');

        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }

    modalClose.addEventListener('click', closeModal);
    // Click outside modal box to close
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
    // ESC key to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });

    // ── Search form ─────────────────────────────────────────────────────────
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const query       = document.getElementById('query').value;
        const mode        = document.getElementById('mode').value;
        const limit       = document.getElementById('limit').value;
        const classFilter = document.getElementById('classFilter').value;

        welcomeMessage.classList.add('hidden');
        resultsContainer.classList.add('hidden');
        loader.classList.remove('hidden');

        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, mode, limit, class_filter: classFilter })
            });

            const data = await response.json();

            if (!response.ok) {
                alert(data.error || "An error occurred during transmission.");
                loader.classList.add('hidden');
                welcomeMessage.classList.remove('hidden');
                return;
            }

            // AI response
            aiResponseHtml.innerHTML = data.ai_response
                ? marked.parse(data.ai_response)
                : "<em>No analysis generated.</em>";

            // Cards
            scpCardsLayout.innerHTML = '';
            resultCountBadge.textContent = data.scps.length;

            data.scps.forEach(scp => {
                const card = document.createElement('div');
                card.className = 'scp-card';

                const objClassStr = scp.object_class.toLowerCase();
                let classBadge = 'object-class';
                if (objClassStr.includes('safe'))   classBadge += ' class-safe';
                else if (objClassStr.includes('euclid')) classBadge += ' class-euclid';
                else if (objClassStr.includes('keter'))  classBadge += ' class-keter';

                const similarityPercent = Math.round(scp.similarity * 100);

                let shortText = scp.text;
                if (shortText.length > 300) shortText = shortText.substring(0, 300) + '...';

                card.innerHTML = `
                    <div class="card-header">
                        <div class="card-title">${scp.scp_id}</div>
                        <div class="${classBadge}">${scp.object_class}</div>
                    </div>
                    <div class="similarity-bar">
                        <span>Relevance</span>
                        <div class="sim-fill-bg">
                            <div class="sim-fill" style="width: ${Math.max(similarityPercent, 10)}%"></div>
                        </div>
                        <span>${similarityPercent}%</span>
                    </div>
                    <div class="card-snippet">${shortText}</div>
                    <div class="card-link-hint">Click to read full entry ↗</div>
                `;

                // Open modal on click
                card.addEventListener('click', () => openModal(scp));
                scpCardsLayout.appendChild(card);
            });

            loader.classList.add('hidden');
            resultsContainer.classList.remove('hidden');

        } catch (err) {
            alert("Network Error: Failed to contact the Foundation Database.");
            loader.classList.add('hidden');
            welcomeMessage.classList.remove('hidden');
        }
    });
});
