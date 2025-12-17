/**
 * Simple HTTP server for Session Fuel
 * Serves the widget and handles session scanning
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3847;
const DIR = __dirname;
const CONVERSATIONS_DIR = path.join(process.env.USERPROFILE, '.gemini', 'antigravity', 'conversations');

// MIME types
const MIME = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.ico': 'image/x-icon'
};

// Get conversations
function getConversations() {
    const conversations = [];
    try {
        const files = fs.readdirSync(CONVERSATIONS_DIR);
        for (const file of files) {
            if (file.endsWith('.pb') && !file.includes('.tmp')) {
                const filePath = path.join(CONVERSATIONS_DIR, file);
                const stats = fs.statSync(filePath);
                conversations.push({
                    id: file.replace('.pb', ''),
                    size: stats.size,
                    modified: stats.mtime,
                    estimatedTokens: Math.round(stats.size / 4)
                });
            }
        }
        conversations.sort((a, b) => b.modified - a.modified);
    } catch (err) {
        console.error('Error reading conversations:', err.message);
    }
    return conversations;
}

const server = http.createServer((req, res) => {
    let filePath = req.url === '/' ? '/index.html' : req.url;
    
    // Handle session API
    if (filePath.startsWith('/api/sessions')) {
        const conversations = getConversations();
        const data = {
            timestamp: new Date().toISOString(),
            activeSession: conversations[0] || null,
            recentSessions: conversations.slice(0, 5)
        };
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(data));
        return;
    }
    
    // Remove query string
    filePath = filePath.split('?')[0];
    
    const fullPath = path.join(DIR, filePath);
    const ext = path.extname(fullPath);
    
    fs.readFile(fullPath, (err, data) => {
        if (err) {
            res.writeHead(404);
            res.end('Not found');
            return;
        }
        res.writeHead(200, { 
            'Content-Type': MIME[ext] || 'text/plain',
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        });
        res.end(data);
    });
});

server.listen(PORT, () => {
    console.log(`\n⛽ Session Fuel running at http://localhost:${PORT}\n`);
    console.log('Press Ctrl+C to stop\n');
    
    // Open in browser
    const { exec } = require('child_process');
    exec(`start http://localhost:${PORT}`);
});
