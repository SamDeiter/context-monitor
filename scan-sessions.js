/**
 * Scans Antigravity conversations folder and finds the most recently modified session
 * Writes the conversation info to a JSON file that the widget can read
 */

const fs = require('fs');
const path = require('path');

const CONVERSATIONS_DIR = path.join(process.env.USERPROFILE, '.gemini', 'antigravity', 'conversations');
const OUTPUT_FILE = path.join(__dirname, 'active-session.json');

function getConversations() {
    const conversations = [];
    
    try {
        const files = fs.readdirSync(CONVERSATIONS_DIR);
        
        for (const file of files) {
            if (file.endsWith('.pb') && !file.includes('.tmp')) {
                const filePath = path.join(CONVERSATIONS_DIR, file);
                const stats = fs.statSync(filePath);
                const id = file.replace('.pb', '');
                
                conversations.push({
                    id,
                    size: stats.size,
                    modified: stats.mtime,
                    // Rough token estimate: ~4 bytes per token
                    estimatedTokens: Math.round(stats.size / 4)
                });
            }
        }
        
        // Sort by most recently modified
        conversations.sort((a, b) => b.modified - a.modified);
        
    } catch (err) {
        console.error('Error reading conversations:', err.message);
    }
    
    return conversations;
}

function writeSessionInfo() {
    const conversations = getConversations();
    
    const data = {
        timestamp: new Date().toISOString(),
        activeSession: conversations[0] || null,
        recentSessions: conversations.slice(0, 5)
    };
    
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(data, null, 2));
    console.log('Session info written to:', OUTPUT_FILE);
    console.log('Active session:', data.activeSession?.id);
    console.log('Estimated tokens:', data.activeSession?.estimatedTokens?.toLocaleString());
}

// Run once and optionally watch for changes
writeSessionInfo();

// If --watch flag, monitor for changes
if (process.argv.includes('--watch')) {
    console.log('\nWatching for conversation changes...');
    fs.watch(CONVERSATIONS_DIR, { persistent: true }, (event, filename) => {
        if (filename && filename.endsWith('.pb')) {
            console.log(`\n[${new Date().toLocaleTimeString()}] Change detected: ${filename}`);
            writeSessionInfo();
        }
    });
}
