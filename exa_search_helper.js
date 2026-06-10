// Exa搜索助手 - 通过 Node.js 调用 mcporter
const { execSync } = require('child_process');
const query = process.argv[2] || '餐饮';
const numResults = parseInt(process.argv[3]) || 5;

try {
  const cmd = `mcporter call 'exa.web_search_exa(query: "${query}", numResults: ${numResults})'`;
  const out = execSync(cmd, { shell: 'bash.exe', encoding: 'utf-8', timeout: 30000 });
  console.log(out);
} catch(e) {
  // Fallback: try without bash
  try {
    const cmd = `mcporter call 'exa.web_search_exa(query: "${query}", numResults: ${numResults})'`;
    const out = execSync(cmd, { shell: true, encoding: 'utf-8', timeout: 30000 });
    console.log(out);
  } catch(e2) {
    console.error('Error:', e2.message);
    process.exit(1);
  }
}
