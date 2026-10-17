import {copyFile, mkdir} from 'node:fs/promises';
await mkdir('dist/assets', {recursive: true});
await copyFile('public/index.html', 'dist/index.html');
await copyFile('src/styles.css', 'dist/assets/styles.css');
console.log('PressPilot client built: dist/ (no runtime third-party dependencies)');

await copyFile('public/favicon.svg', 'dist/assets/favicon.svg');
