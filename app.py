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

def load_videos():
    """Load videos from filesystem into database"""
    conn = sqlite3.connect('likes.db')
    cursor = conn.cursor()

    video_files = []

    # Load regular videos from videos directory
    videos_dir = 'videos'
    if os.path.exists(videos_dir):
        print(f"Scanning videos directory: {videos_dir}")
        for filename in os.listdir(videos_dir):
            if filename.lower().endswith('.mp4'):
                filepath = os.path.join(videos_dir, filename)
                if os.path.isfile(filepath):
                    video_files.append((f'videos/{filename}', 0))
                    print(f"Found video: {filename}")

    # Load ads from ads directory
    ads_dir = 'ads'
    if os.path.exists(ads_dir):
        print(f"Scanning ads directory: {ads_dir}")
        for filename in os.listdir(ads_dir):
            if filename.lower().endswith('.mp4'):
                filepath = os.path.join(ads_dir, filename)
                if os.path.isfile(filepath):
                    video_files.append((f'ads/{filename}', 1))
                    print(f"Found ad: {filename}")

    # Load videos from static/videos directory
    static_videos_dir = 'static/videos'
    if os.path.exists(static_videos_dir):
        print(f"Scanning static videos directory: {static_videos_dir}")
        for filename in os.listdir(static_videos_dir):
            if filename.lower().endswith('.mp4'):
                filepath = os.path.join(static_videos_dir, filename)
                if os.path.isfile(filepath):
                    video_files.append((f'static/videos/{filename}', 0))
                    print(f"Found video in static: {filename}")

    # Load ads from static/ads directory
    static_ads_dir = 'static/ads'
    if os.path.exists(static_ads_dir):
        print(f"Scanning static ads directory: {static_ads_dir}")
        for filename in os.listdir(static_ads_dir):
            if filename.lower().endswith('.mp4'):
                filepath = os.path.join(static_ads_dir, filename)
                if os.path.isfile(filepath):
                    video_files.append((f'static/ads/{filename}', 1))
                    print(f"Found ad in static: {filename}")

    # Load videos directly from static directory
    static_dir = 'static'
    if os.path.exists(static_dir):
        print(f"Scanning static root directory: {static_dir}")
        for filename in os.listdir(static_dir):
            if filename.lower().endswith('.mp4'):
                filepath = os.path.join(static_dir, filename)
                if os.path.isfile(filepath):
                    # Check if filename suggests it's an ad
                    is_ad = 1 if filename.lower().startswith('ad') else 0
                    video_files.append((f'static/{filename}', is_ad))
                    print(f"Found video in static root: {filename} (is_ad: {is_ad})")
    
    print(f"Total videos found: {len(video_files)}")
    
    # Clear existing records to avoid duplicates
    cursor.execute('DELETE FROM records')
    
    # Insert videos into database, avoiding duplicates
    added_count = 0
    for filepath, is_ad in video_files:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO records (filename, is_ad, total_likes) 
                VALUES (?, ?, 0)
            ''', (filepath, is_ad))
            
            # Check if the insert was successful
            if cursor.rowcount > 0:
                added_count += 1
                print(f"Added to database: {filepath} (is_ad: {is_ad})")
            else:
                print(f"Skipped duplicate: {filepath}")
        except sqlite3.Error as e:
            print(f"Error inserting {filepath}: {e}")

    conn.commit()
    conn.close()
    print(f"Successfully loaded {added_count} videos into database")
    return added_count

# Routes
@app.route('/')
def index():
    return send_from_directory('.', 'static/index.html')

@app.route('/videos/<filename>')
def serve_video(filename):
    # Try videos directory first, then static/videos
    if os.path.exists(os.path.join('videos', filename)):
        return send_from_directory('videos', filename)
    elif os.path.exists(os.path.join('static/videos', filename)):
        return send_from_directory('static/videos', filename)
    else:
        return "Video not found", 404

@app.route('/ads/<filename>')
def serve_ad(filename):
    # Try ads directory first, then static/ads
    if os.path.exists(os.path.join('ads', filename)):
        return send_from_directory('ads', filename)
    elif os.path.exists(os.path.join('static/ads', filename)):
        return send_from_directory('static/ads', filename)
    else:
        return "Ad not found", 404

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/api/get_user_id')
def get_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    print(f"User ID: {session['user_id']}")
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
    
    print(f"Returning {len(video_list)} videos")
    return jsonify(video_list)

@app.route('/api/like', methods=['POST'])
def toggle_like():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        video_id = data.get('video_id')
        
        print(f"Like request - User: {user_id}, Video: {video_id}")
        
        # If no user_id provided, get it from session
        if not user_id:
            if 'user_id' not in session:
                session['user_id'] = str(uuid.uuid4())
            user_id = session['user_id']
        
        if not video_id:
            return jsonify({'error': 'Missing video_id'}), 400
        
        conn = sqlite3.connect('likes.db')
        cursor = conn.cursor()
        
        # Verify video exists
        cursor.execute('SELECT id FROM records WHERE id = ?', (video_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Video not found'}), 404
        
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
            print(f"Unliked video {video_id}")
        else:
            # Like - add the like
            cursor.execute('INSERT INTO user_likes (user_id, video_id) VALUES (?, ?)', 
                           (user_id, video_id))
            cursor.execute('UPDATE records SET total_likes = total_likes + 1 WHERE id = ?', 
                           (video_id,))
            liked = True
            print(f"Liked video {video_id}")
        
        # Get updated like count
        cursor.execute('SELECT total_likes FROM records WHERE id = ?', (video_id,))
        result = cursor.fetchone()
        total_likes = result[0] if result else 0
        
        conn.commit()
        conn.close()
        
        response = {
            'liked': liked,
            'total_likes': total_likes,
            'user_id': user_id
        }
        print(f"Like response: {response}")
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in toggle_like: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
            .refresh-btn { background: #4444ff; color: white; border: none; border-radius: 3px; }
            .refresh-btn:hover { background: #0000cc; }
            .status { margin: 10px 0; padding: 10px; background: #e6f3ff; border-radius: 3px; }
            .summary { background: #e6ffe6; padding: 15px; margin: 10px 0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>Video Website Admin</h1>
        <div class="status" id="status">Loading...</div>
        
        <div class="summary" id="summary">
            Loading summary...
        </div>
        
        <button class="refresh-btn" onclick="loadStats()">Refresh Stats</button>
        <button class="reset-btn" onclick="resetStats()">Reset All Stats</button>
        <button onclick="refreshVideos()">Refresh Video List</button>
        
        <div class="stats" id="stats">
            Loading stats...
        </div>
        
        <div class="video-list" id="videoList">
            Loading videos...
        </div>
        
        <script>
            let isPolling = false;
            
            function loadStats() {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('summary').innerHTML = `
                            <h2>Summary</h2>
                            <p><strong>Total Videos:</strong> ${data.total_videos}</p>
                            <p><strong>Total Ads:</strong> ${data.total_ads}</p>
                            <p><strong>Total Items:</strong> ${data.total_videos + data.total_ads}</p>
                        `;
                        
                        document.getElementById('stats').innerHTML = `
                            <h2>Advertisement Statistics</h2>
                            <p><strong>Total Likes on Ads:</strong> ${data.total_ad_likes}</p>
                            <p><strong>Unique Users Who Liked Ads:</strong> ${data.unique_users_liked_ads}</p>
                            <h3>Ad Performance:</h3>
                            ${data.ad_videos.length > 0 ? data.ad_videos.map(ad => `
                                <div style="margin: 10px 0; padding: 10px; background: #fff; border-radius: 3px;">
                                    <strong>${ad.filename}</strong><br>
                                    Likes: ${ad.likes}
                                </div>
                            `).join('') : '<p>No ads found</p>'}
                        `;
                        
                        document.getElementById('status').innerHTML = `
                            <strong>Status:</strong> Connected - Last updated: ${new Date().toLocaleTimeString()}
                        `;
                    })
                    .catch(error => {
                        console.error('Error loading stats:', error);
                        document.getElementById('stats').innerHTML = 'Error loading stats';
                        document.getElementById('status').innerHTML = `
                            <strong>Status:</strong> Error loading stats - ${new Date().toLocaleTimeString()}
                        `;
                    });
            }
            
            function loadVideos() {
                fetch('/api/videos')
                    .then(response => response.json())
                    .then(videos => {
                        const regularVideos = videos.filter(v => !v.is_ad);
                        
                        const videoListHTML = `
                            <h2>All Videos (${regularVideos.length} total)</h2>
                            ${regularVideos.map(video => `
                                <div class="video-item">
                                    <strong>${video.filename}</strong> - ${video.total_likes} likes
                                </div>
                            `).join('')}
                        `;
                        
                        document.getElementById('videoList').innerHTML = videoListHTML;
                    })
                    .catch(error => {
                        console.error('Error loading videos:', error);
                        document.getElementById('videoList').innerHTML = 'Error loading videos';
                    });
            }
            
            function resetStats() {
                if (confirm('Are you sure you want to reset all stats? This will delete all likes and user data.')) {
                    fetch('/api/reset', { method: 'POST' })
                        .then(response => response.json())
                        .then(data => {
                            alert(data.message);
                            loadStats();
                            loadVideos();
                        })
                        .catch(error => {
                            console.error('Error resetting stats:', error);
                            alert('Error resetting stats');
                        });
                }
            }
            
            function refreshVideos() {
                if (confirm('This will refresh the video list from your file system. Continue?')) {
                    fetch('/api/refresh_videos', { method: 'POST' })
                        .then(response => response.json())
                        .then(data => {
                            alert(data.message);
                            loadStats();
                            loadVideos();
                        })
                        .catch(error => {
                            console.error('Error refreshing videos:', error);
                            alert('Error refreshing videos');
                        });
                }
            }
            
            function startPolling() {
                if (!isPolling) {
                    isPolling = true;
                    // Poll every 5 seconds for real-time updates
                    setInterval(() => {
                        loadStats();
                        loadVideos();
                    }, 5000);
                }
            }
            
            // Load data on page load
            loadStats();
            loadVideos();
            
            // Start real-time polling
            startPolling();
        </script>
    </body>
    </html>
    '''

@app.route('/api/reset', methods=['POST'])
def reset_stats():
    """Reset all statistics"""
    try:
        conn = sqlite3.connect('likes.db')
        cursor = conn.cursor()
        
        # Clear all likes
        cursor.execute('DELETE FROM user_likes')
        cursor.execute('UPDATE records SET total_likes = 0')
        
        conn.commit()
        conn.close()
        
        print("All statistics reset")
        return jsonify({'message': 'All statistics have been reset successfully'})
    except Exception as e:
        print(f"Error resetting stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh_videos', methods=['POST'])
def refresh_videos():
    """Refresh video list from file system"""
    try:
        count = load_videos()
        return jsonify({'message': f'Video list refreshed successfully. Loaded {count} videos.'})
    except Exception as e:
        print(f"Error refreshing videos: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add this route to handle videos directly in static folder
@app.route('/<filename>')
def serve_root_video(filename):
    """Serve video files directly from static directory"""
    if filename.endswith('.mp4'):
        return send_from_directory('static', filename)
    return "File not found", 404

@app.route('/api/stats')
def get_stats():
    """Get statistics for admin panel"""
    try:
        conn = sqlite3.connect('likes.db')
        cursor = conn.cursor()
        
        # Get total videos and ads count
        cursor.execute('SELECT COUNT(*) FROM records WHERE is_ad = 0')
        total_videos = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM records WHERE is_ad = 1')
        total_ads = cursor.fetchone()[0]
        
        # Get total likes on ads
        cursor.execute('SELECT SUM(total_likes) FROM records WHERE is_ad = 1')
        result = cursor.fetchone()
        total_ad_likes = result[0] if result[0] else 0
        
        # Get unique users who liked ads
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) 
            FROM user_likes 
            JOIN records ON user_likes.video_id = records.id 
            WHERE records.is_ad = 1
        ''')
        unique_users_liked_ads = cursor.fetchone()[0]
        
        # Get individual ad performance
        cursor.execute('''
            SELECT filename, total_likes 
            FROM records 
            WHERE is_ad = 1 
            ORDER BY total_likes DESC
        ''')
        ad_videos = []
        for row in cursor.fetchall():
            ad_videos.append({
                'filename': row[0],
                'likes': row[1]
            })
        
        conn.close()
        
        stats = {
            'total_videos': total_videos,
            'total_ads': total_ads,
            'total_ad_likes': total_ad_likes,
            'unique_users_liked_ads': unique_users_liked_ads,
            'ad_videos': ad_videos
        }
        
        print(f"Stats returned: {stats}")
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error in get_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
if __name__ == '__main__':
    init_db()
    video_count = load_videos()
    print(f"Database initialized with {video_count} videos")
    print("Starting server...")
    print("Main site: http://localhost:8000")
    print("Admin panel: http://localhost:8000/admin")
    print("To reset database completely, delete 'likes.db' file before running")
    app.run(debug=True, host='0.0.0.0', port=8000)  