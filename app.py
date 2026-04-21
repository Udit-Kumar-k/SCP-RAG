import os
from flask import Flask, request, jsonify, render_template
from scp_rag import load_or_create_db, retrieve_scps, brainstorm_with_ai, EMBED_MODEL
from sentence_transformers import SentenceTransformer

app = Flask(__name__)

# Initialize DB and Embedder globally once
print("Initializing Database and AI Models (this might take a few moments)...")
collection = load_or_create_db()
embedder = SentenceTransformer(EMBED_MODEL)
print("Initialization Complete! Launching Terminal...")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_scp():
    data = request.json
    query = data.get('query', '')
    mode = data.get('mode', 'find')
    limit = int(data.get('limit', 5))
    class_filter = data.get('class_filter', '').strip()
    
    if class_filter.lower() in ['', 'skip', 'all']:
        class_filter = None

    if not query:
        return jsonify({"error": "Transmission Failure: Query cannot be empty."}), 400

    try:
        # Retrieve the relevant SCP entries
        scps = retrieve_scps(
            query=query, 
            collection=collection, 
            embedder=embedder, 
            top_k=limit, 
            object_class_filter=class_filter
        )
        
        # Pass to AI to brainstorm
        ai_response = brainstorm_with_ai(query, scps, mode=mode)
        
        return jsonify({
            "scps": scps,
            "ai_response": ai_response
        })
    except Exception as e:
        return jsonify({"error": f"Classified Error: {str(e)}"}), 500

if __name__ == '__main__':
    # use_reloader=False fixes the WinError 10038 socket crash on Windows
    app.run(debug=True, port=5000, use_reloader=False)
