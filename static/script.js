document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('searchForm');
    const loader = document.getElementById('loader');
    const resultsContainer = document.getElementById('resultsContainer');
    const welcomeMessage = document.getElementById('welcomeMessage');
    const scpCardsLayout = document.getElementById('scpCards');
    const aiResponseHtml = document.getElementById('aiResponse');
    const resultCountBadge = document.getElementById('resultCount');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Get values
        const query = document.getElementById('query').value;
        const mode = document.getElementById('mode').value;
        const limit = document.getElementById('limit').value;
        const classFilter = document.getElementById('classFilter').value;

        // UI Updates
        welcomeMessage.classList.add('hidden');
        resultsContainer.classList.add('hidden');
        loader.classList.remove('hidden');

        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    mode: mode,
                    limit: limit,
                    class_filter: classFilter
                })
            });

            const data = await response.json();

            if (!response.ok) {
                alert(data.error || "An error occurred during transmission.");
                loader.classList.add('hidden');
                welcomeMessage.classList.remove('hidden');
                return;
            }

            // Populate AI Response using Marked.js for markdown parsing
            if (data.ai_response) {
                aiResponseHtml.innerHTML = marked.parse(data.ai_response);
            } else {
                aiResponseHtml.innerHTML = "<em>No analysis generated.</em>";
            }

            // Populate Cards
            scpCardsLayout.innerHTML = '';
            resultCountBadge.textContent = data.scps.length;

            data.scps.forEach(scp => {
                const card = document.createElement('div');
                card.className = 'scp-card';

                // Determine class styling
                const objClassStr = scp.object_class.toLowerCase();
                let classBadge = 'object-class';
                if (objClassStr.includes('safe')) classBadge += ' class-safe';
                else if (objClassStr.includes('euclid')) classBadge += ' class-euclid';
                else if (objClassStr.includes('keter')) classBadge += ' class-keter';

                const similarityPercent = Math.round(scp.similarity * 100);

                let shortText = scp.text;
                if(shortText.length > 300) {
                    shortText = shortText.substring(0, 300) + '...';
                }

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
                `;
                scpCardsLayout.appendChild(card);
            });

            // Reveal
            loader.classList.add('hidden');
            resultsContainer.classList.remove('hidden');

        } catch (err) {
            alert("Network Error: Failed to contact the Foundation Database.");
            loader.classList.add('hidden');
            welcomeMessage.classList.remove('hidden');
        }
    });
});
