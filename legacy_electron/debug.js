// Debug script to check what electron module exports
console.log('Starting debug...');
console.log('Process type:', process.type);
console.log('Process versions:', process.versions);

try {
    const electron = require('electron');
    console.log('Electron module:', electron);
    console.log('Electron keys:', Object.keys(electron || {}));
} catch (e) {
    console.error('Error requiring electron:', e);
}
