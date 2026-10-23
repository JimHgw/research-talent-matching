import { readFile, readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { transformWithEsbuild } from 'vite';

// Vite's installed Rollup parser lets this check inspect compiled JSX without
// adding a second parser dependency or guessing at source text with regexes.
const { parseAst } = createRequire(import.meta.resolve('vite'))('rollup/parseAst');
const textAttributes = new Set(['label', 'hint', 'title', 'placeholder', 'aria-label']);
const brandText = new Set(['banana', 'H18ABANANA']);
const humanText = (value) => typeof value === 'string' && /[A-Za-z]{2}/.test(value);

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (
    await Promise.all(
      entries.map((entry) => {
        const path = new URL(entry.name + (entry.isDirectory() ? '/' : ''), directory);
        if (entry.isDirectory()) return sourceFiles(path);
        return entry.name.endsWith('.jsx') ? [path] : [];
      })
    )
  ).flat();
}

export async function auditInterfaceMessages(root = new URL('../src/', import.meta.url)) {
  const problems = [];
  const keys = new Set();
  for (const file of await sourceFiles(root)) {
    const source = await readFile(file, 'utf8');
    const { code } = await transformWithEsbuild(source, fileURLToPath(file), {
      loader: 'jsx',
      jsx: 'transform',
    });
    const ast = parseAst(code);
    function visible(node, purpose) {
      if (!node) return;
      if (node.type === 'Literal' && humanText(node.value) && !brandText.has(node.value.trim()))
        problems.push({ file: fileURLToPath(file), message: node.value, purpose });
      if (node.type === 'TemplateLiteral' && node.quasis.some((q) => humanText(q.value.cooked)))
        problems.push({ file: fileURLToPath(file), message: 'Untranslated template', purpose });
      if (node.type === 'ConditionalExpression') {
        visible(node.consequent, purpose);
        visible(node.alternate, purpose);
      }
      if (node.type === 'LogicalExpression') visible(node.right, purpose);
    }
    function visit(node) {
      if (!node || typeof node !== 'object') return;
      if (
        node.type === 'CallExpression' &&
        ['t', 'notify', 'setMessage'].includes(node.callee?.name)
      ) {
        function collect(value) {
          if (value?.type === 'Literal' && humanText(value.value)) keys.add(value.value);
          if (value?.type === 'ConditionalExpression') {
            collect(value.consequent);
            collect(value.alternate);
          }
        }
        collect(node.arguments[0]);
      }
      if (node.type === 'CallExpression' && node.callee?.property?.name === 'confirm')
        visible(node.arguments[0], 'confirmation');
      if (
        node.type === 'CallExpression' &&
        node.callee?.type === 'MemberExpression' &&
        node.callee.property.name === 'createElement'
      ) {
        for (const child of node.arguments.slice(2)) visible(child, 'text');
        const props = node.arguments[1];
        if (props?.type === 'ObjectExpression')
          for (const prop of props.properties)
            if (textAttributes.has(prop.key?.name || prop.key?.value)) {
              // Example email addresses are data, not prose.
              if (
                (prop.key?.name || prop.key?.value) === 'placeholder' &&
                /@/.test(prop.value?.value || '')
              )
                continue;
              visible(prop.value, 'attribute');
            }
      }
      for (const value of Object.values(node)) {
        if (Array.isArray(value)) value.forEach(visit);
        else if (value && typeof value === 'object') visit(value);
      }
    }
    visit(ast);
  }
  return { problems, keys: [...keys] };
}
