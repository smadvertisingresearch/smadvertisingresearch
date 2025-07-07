from flask import Flask, render_template, request, jsonify, send_from_directory, session
import uuid
import sqlite3
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rio_sophie_claire_secure_key_2024'

def init_db():
    conn = sqlite3.connect('likes.db')
    cursor = conn.cursor()
    
    # Create records table (videos and ads)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE,
            is_ad INTEGER DEFAULT 0,
            total_likes INTEGER DEFAULT 0
        )
    ''')

    # Create user_likes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_likes(
            id INTEGER PRIMARY KEY,
            user_id TEXT,
            video_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(video_id) REFERENCES records(id),
            UNIQUE(user_id, video_id)
        )
    ''')

    conn.commit()
    conn.close()

def reset_database():
    """Reset the database to start fresh"""
    if os.path.exists('likes.db'):
        os.remove('likes.db')
    init_db()

def load_videos():
    conn = sqlite3.connect('likes.db')
    cursor = conn.cursor()

    video_files = []

    # Load regular videos
    if os.path.exists('static/videos'):
        for filename in os.listdir('static/videos'):
            if filename.endswith('.mp4'):
                video_files.append(('videos/' + filename, 0))

    # Load ads
    if os.path.exists('static/ads'):
        for filename in os.listdir('static/ads'):
            if filename.endswith('.mp4'):
                video_files.append(('ads/' + filename, 1))
    
    # Insert videos into database ONLY if they don't exist
    for filepath, is_ad in video_files:
        cursor.execute('''
            INSERT OR IGNORE INTO records (filename, is_ad, total_likes) 
            VALUES (?, ?, 0)
        ''', (filepath, is_ad))

    conn.commit()
    conn.close()

# Routes
@app.route('/')
def index():
    return send_from_directory('.', 'static/index.html')

@app.route('/videos/<filename>')
def serve_video(filename):
    return send_from_directory('static/videos', filename)

@app.route('/ads/<filename>')
def serve_ad(filename):
    return send_from_directory('static/ads', filename)

@app.route('/api/get_user_id')
def get_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return jsonify({'user_id': session['user_id']})

@app.route('/api/videos')
def get_videos():
    conn = sqlite3.connect('likes.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, filename, is_ad, total_likes FROM records ORDER BY id')
    videos = cursor.fetchall()
    
    conn.close()
    
    video_list = []
    for video in videos:
        video_list.append({
            'id': video[0],
            'filename': video[1],
            'is_ad': bool(video[2]),
            'total_likes': video[3]
        })
    
    return jsonify(video_list)

@app.route('/api/like', methods=['POST'])
def toggle_like():
    data = request.get_json()
    user_id = data.get('user_id')
    video_id = data.get('video_id')
    
    # If no user_id provided, get it from session
    if not user_id:
        if 'user_id' not in session:
            session['user_id'] = str(uuid.uuid4())
        user_id = session['user_id']
    
    if not video_id:
        return jsonify({'error': 'Missing video_id'}), 400
    
    conn = sqlite3.connect('likes.db')
    cursor = conn.cursor()
    
    # Check if user already liked this video
    cursor.execute('SELECT id FROM user_likes WHERE user_id = ? AND video_id = ?', 
                   (user_id, video_id))
    existing_like = cursor.fetchone()
    
    if existing_like:
        # Unlike - remove the like
        cursor.execute('DELETE FROM user_likes WHERE user_id = ? AND video_id = ?', 
                       (user_id, video_id))
        cursor.execute('UPDATE records SET total_likes = total_likes - 1 WHERE id = ? AND total_likes > 0', 
                       (video_id,))
        liked = False
    else:
        # Like - add the like
        cursor.execute('INSERT INTO user_likes (user_id, video_id) VALUES (?, ?)', 
                       (user_id, video_id))
        cursor.execute('UPDATE records SET total_likes = total_likes + 1 WHERE id = ?', 
                       (video_id,))
        liked = True
    
    # Get updated like count
    cursor.execute('SELECT total_likes FROM records WHERE id = ?', (video_id,))
    result = cursor.fetchone()
    total_likes = result[0] if result else 0
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'liked': liked,
        'total_likes': total_likes,
        'user_id': user_id
    })

@app.route('/api/stats')
def get_stats():
    conn = sqlite3.connect('likes.db')
    cursor = conn.cursor()
    
    # Get total likes on advertisement videos only
    cursor.execute('SELECT SUM(total_likes) FROM records WHERE is_ad = 1')
    ad_likes = cursor.fetchone()[0] or 0
    
    # Get total unique users who liked ads
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id) FROM user_likes 
        JOIN records ON user_likes.video_id = records.id 
        WHERE records.is_ad = 1
    ''')
    unique_users = cursor.fetchone()[0] or 0
    
    # Get ad videos with their like counts
    cursor.execute('''
        SELECT filename, total_likes FROM records 
        WHERE is_ad = 1 
        ORDER BY total_likes DESC
    ''')
    ad_videos = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'total_ad_likes': ad_likes,
        'unique_users_liked_ads': unique_users,
        'ad_videos': [{'filename': v[0], 'likes': v[1]} for v in ad_videos]
    })

@app.route('/admin')
def admin():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .stats { background: #f0f0f0; padding: 20px; margin: 20px 0; border-radius: 5px; }
            .video-list { margin: 20px 0; }
            .video-item { padding: 10px; margin: 5px 0; background: #f9f9f9; border-radius: 3px; }
            .ad-video { background: #ffe6e6; }
            button { padding: 10px 20px; margin: 10px 0; cursor: pointer; }
            .reset-btn { background: #ff4444; color: white; border: none; border-radius: 3px; }
            .reset-btn:hover { background: #cc0000; }
        </style>
    </head>
    <body>
        <h1>Video Website Admin</h1>
        <button onclick="loadStats()">Refresh Stats</button>
        <button class="reset-btn" onclick="resetStats()">Reset All Stats</button>
        
        <div class="stats" id="stats">
            Loading stats...
        </div>
        
        <div class="video-list" id="videoList">
            Loading videos...
        </div>
        
        <script>
            function loadStats() {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('stats').innerHTML = `
                            <h2>Advertisement Statistics</h2>
                            <p><strong>Total Likes on Ads:</strong> ${data.total_ad_likes}</p>
                            <p><strong>Unique Users Who Liked Ads:</strong> ${data.unique_users_liked_ads}</p>
                        `;
                    });
                
                fetch('/api/videos')
                    .then(response => response.json())
                    .then(videos => {
                        const videoListHTML = videos.map(video => `
                            <div class="video-item ${video.is_ad ? 'ad-video' : ''}">
                                <strong>${video.filename}</strong> 
                                ${video.is_ad ? '(Advertisement)' : '(Regular)'} 
                                - ${video.total_likes} likes
                            </div>
                        `).join('');
                        
                        document.getElementById('videoList').innerHTML = 
                            '<h2>All Videos</h2>' + videoListHTML;
                    });
            }
            
            function resetStats() {
                if (confirm('Are you sure you want to reset all stats? This will delete all likes and user data.')) {
                    fetch('/api/reset', { method: 'POST' })
                        .then(response => response.json())
                        .then(data => {
                            alert(data.message);
                            loadStats();
                        });
                }
            }
            
            // Load stats on page load
            loadStats();
        </script>
    </body>
    </html>
    '''

@app.route('/api/reset', methods=['POST'])
def reset_stats():
    """Reset all statistics"""
    conn = sqlite3.connect('likes.db')
    cursor = conn.cursor()
    
    # Clear all likes
    cursor.execute('DELETE FROM user_likes')
    cursor.execute('UPDATE records SET total_likes = 0')
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'All statistics have been reset successfully'})

if __name__ == '__main__':
    init_db()
    load_videos()
    print("Starting server...")
    print("Main site: http://localhost:8000")
    print("Admin panel: http://localhost:8000/admin")
    print("To reset database completely, delete 'likes.db' file before running")
    app.run(debug=True, host='0.0.0.0', port=8000)