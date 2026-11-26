#!/usr/bin/env node
/* T4 node 侧：从权威模板抽取 HEALTH_WEIGHTS / round1 / recomputeHealth，
   与 Python canonical 读同一份 fixture 后逐栏输出，供比较器核对。*/
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const root = process.argv[2] || path.resolve(__dirname, '../..');
const tpl = fs.readFileSync(path.join(root, 'templates/index.html.template'), 'utf8');
const fixture = JSON.parse(fs.readFileSync(
  path.join(root, 'tests/fixtures/health_equivalence.json'), 'utf8'));

function block(src, signature) {
  const at = src.indexOf(signature);
  if (at < 0) throw new Error('模板缺少 ' + signature);
  const open = src.indexOf('{', at + signature.length - 1);
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === '{') depth++;
    if (src[i] === '}' && --depth === 0) return src.slice(at, i + 1);
  }
  throw new Error('模板代码块未闭合：' + signature);
}
function literal(src, signature) {
  const at = src.indexOf(signature);
  if (at < 0) throw new Error('模板缺少 ' + signature);
  const open = src.indexOf('{', at);
  let depth = 0;
  for (let i = open; i < src.length; i++) {
    if (src[i] === '{') depth++;
    if (src[i] === '}' && --depth === 0) return src.slice(open, i + 1);
  }
  throw new Error('模板字面量未闭合：' + signature);
}

const parts = [
  'const HEALTH_WEIGHTS=' + literal(tpl, 'const HEALTH_WEIGHTS=') + ';',
  "const HEALTH_NA_TEST='n/a (未投影)';",
  "const HEALTH_NA_VERIFY='n/a (无能力点)';",
  block(tpl, 'function round1('),
  block(tpl, 'function recomputeHealth('),
];
const script = new vm.Script(parts.join('\n'));

const out = fixture.cases.map(c => {
  const sandbox = {cm: c.model, d: c.ledger, overrides: undefined};
  const ctx = vm.createContext(sandbox);
  script.runInContext(ctx);
  const h = sandbox.recomputeHealth(c.model, c.ledger);
  return {name: c.name, dimensions: h.dimensions,
          overall: h.overall, coverage: h.coverage};
});
process.stdout.write(JSON.stringify(out, null, 2));
