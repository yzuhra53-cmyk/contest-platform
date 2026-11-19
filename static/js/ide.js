// Kontest kod muharriri: rangli sintaksis, avto-maslahatlar, ishga tushirish va konsol.
// CodeMirror CDN'dan yuklanmasa ham sahifa oddiy textarea bilan ishlayveradi.
(function () {
  const PY_KEYWORDS = ['and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'False', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None', 'nonlocal', 'not',
    'or', 'pass', 'raise', 'return', 'True', 'try', 'while', 'with', 'yield'];
  const PY_BUILTINS = ['abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod', 'enumerate', 'filter', 'float',
    'format', 'hex', 'input', 'int', 'isinstance', 'len', 'list', 'map', 'max', 'min', 'oct', 'ord', 'pow', 'print',
    'range', 'reversed', 'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'zip', 'sys', 'math', 'collections',
    'heapq', 'bisect', 'itertools', 'functools', 'deque', 'defaultdict', 'Counter', 'heappush', 'heappop',
    'bisect_left', 'bisect_right', 'gcd', 'sqrt', 'inf', 'setrecursionlimit', 'stdin', 'readline'];
  const PY_METHODS = ['append', 'extend', 'insert', 'pop', 'remove', 'sort', 'reverse', 'index', 'count', 'copy',
    'clear', 'split', 'strip', 'rstrip', 'lstrip', 'join', 'replace', 'find', 'upper', 'lower', 'isdigit',
    'isalpha', 'startswith', 'endswith', 'keys', 'values', 'items', 'get', 'add', 'discard', 'update',
    'appendleft', 'popleft', 'read', 'readline', 'most_common'];
  const PY_SNIPPETS = [
    {displayText: 'n = int(input())', text: 'n = int(input())'},
    {displayText: 'a = list(map(int, input().split()))', text: 'a = list(map(int, input().split()))'},
    {displayText: 'data = sys.stdin.read().split()', text: 'data = sys.stdin.read().split()'},
    {displayText: 'for i in range(n):', text: 'for i in range(n):\n    '},
    {displayText: 'def solve():', text: 'def solve():\n    '},
    {displayText: "if __name__ == '__main__':", text: "if __name__ == '__main__':\n    solve()"},
    {displayText: 'from collections import deque, defaultdict, Counter', text: 'from collections import deque, defaultdict, Counter'},
    {displayText: "print(' '.join(map(str, a)))", text: "print(' '.join(map(str, a)))"},
  ];
  const CPP_KEYWORDS = ['auto', 'bool', 'break', 'case', 'char', 'const', 'continue', 'default', 'do', 'double',
    'else', 'false', 'float', 'for', 'if', 'int', 'long', 'namespace', 'nullptr', 'return', 'short', 'signed',
    'sizeof', 'static', 'struct', 'switch', 'true', 'typedef', 'unsigned', 'using', 'void', 'while', 'include',
    'std', 'string', 'vector', 'pair', 'map', 'set', 'unordered_map', 'unordered_set', 'queue', 'stack', 'deque',
    'priority_queue', 'cin', 'cout', 'endl', 'getline', 'sort', 'reverse', 'min', 'max', 'swap', 'abs',
    'lower_bound', 'upper_bound', 'accumulate', 'make_pair', 'greater', 'memset', 'fill', 'iota', 'unique',
    'binary_search', 'to_string', 'stoi', 'stoll', 'gcd', 'sqrt', 'INT_MAX', 'LLONG_MAX', 'ios', 'sync_with_stdio'];
  const CPP_METHODS = ['push_back', 'pop_back', 'emplace_back', 'size', 'empty', 'begin', 'end', 'rbegin', 'rend',
    'front', 'back', 'insert', 'erase', 'find', 'count', 'clear', 'resize', 'assign', 'push', 'pop', 'top',
    'first', 'second', 'substr', 'length', 'c_str', 'at'];
  const CPP_SNIPPETS = [
    {displayText: '#include <bits/stdc++.h>', text: '#include <bits/stdc++.h>'},
    {displayText: 'using namespace std;', text: 'using namespace std;'},
    {displayText: 'for (int i = 0; i < n; i++)', text: 'for (int i = 0; i < n; i++) {\n    \n}'},
    {displayText: 'vector<int> a(n);', text: 'vector<int> a(n);'},
    {displayText: 'ios::sync_with_stdio(false); cin.tie(nullptr);', text: 'ios::sync_with_stdio(false);\ncin.tie(nullptr);'},
    {displayText: 'long long', text: 'long long'},
  ];
  const TEMPLATES = {
    python: 'import sys\n\n\ndef main():\n    data = sys.stdin.read().split()\n    n = int(data[0])\n    \n\n\nmain()\n',
    cpp: '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n\n    int n;\n    cin >> n;\n    \n    return 0;\n}\n',
  };
  const STATUS = {
    ok: ['Bajarildi', 'ok'],
    compile_error: ['Kompilyatsiya xatosi', 'bad'],
    runtime_error: ['Runtime Error', 'bad'],
    time_limit: ['Vaqt limiti oshdi', 'bad'],
    output_limit: ['Chiqish juda katta', 'bad'],
  };
  const normalize = (text) => (text || '').split(/\s+/).filter(Boolean).join(' ');

  function hintsFor(cm, language) {
    const cursor = cm.getCursor();
    const line = cm.getLine(cursor.line);
    let start = cursor.ch;
    while (start > 0 && /[\w#]/.test(line.charAt(start - 1))) start -= 1;
    const word = line.slice(start, cursor.ch);
    const afterDot = start > 0 && line.charAt(start - 1) === '.';
    const lower = word.toLowerCase();
    const seen = new Set();
    const list = [];
    const push = (item) => {
      const text = typeof item === 'string' ? item : item.text;
      const shown = typeof item === 'string' ? item : item.displayText;
      if (text === word || seen.has(shown)) return;
      if (lower && !shown.toLowerCase().startsWith(lower)) return;
      seen.add(shown);
      list.push(item);
    };
    if (afterDot) {
      (language === 'cpp' ? CPP_METHODS : PY_METHODS).forEach(push);
    } else {
      (language === 'cpp' ? CPP_SNIPPETS : PY_SNIPPETS).forEach(push);
      (language === 'cpp' ? CPP_KEYWORDS : PY_KEYWORDS.concat(PY_BUILTINS)).forEach(push);
    }
    // Hujjatdagi o'zingiz yozgan nomlar (o'zgaruvchilar, funksiyalar).
    const own = new Set(cm.getValue().match(/[A-Za-z_]\w{2,}/g) || []);
    own.forEach(push);
    return {list: list.slice(0, 40), from: CodeMirror.Pos(cursor.line, start), to: cursor};
  }

  window.initIde = function (options) {
    const textarea = document.getElementById('source_code');
    const languageSelect = document.getElementById('language');
    const fileLabel = document.getElementById('ideFile');
    const stdin = document.getElementById('ideStdin');
    const output = document.getElementById('ideOutput');
    const runStatus = document.getElementById('ideRunStatus');
    const runButton = document.getElementById('ideRun');
    const csrf = document.querySelector('meta[name="csrf-token"]').content;
    let lastTyped = 0;
    let cm = null;

    // Avtomatik qoralama: sahifa yangilansa ham yozilgan kod yo'qolmaydi.
    try {
      const draft = localStorage.getItem(options.draftKey);
      if (draft && draft !== options.submittedCode) textarea.value = draft;
    } catch (error) { /* localStorage yopiq bo'lishi mumkin */ }

    const getCode = () => (cm ? cm.getValue() : textarea.value);
    const language = () => languageSelect.value;
    function saveDraft() {
      try { localStorage.setItem(options.draftKey, getCode()); } catch (error) { /* bo'sh */ }
    }

    if (window.CodeMirror) {
      let fontSize = Number(localStorage.getItem('ide-font') || 15);
      cm = CodeMirror.fromTextArea(textarea, {
        mode: language() === 'cpp' ? 'text/x-c++src' : 'python',
        theme: 'dracula',
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        matchBrackets: true,
        autoCloseBrackets: true,
        styleActiveLine: true,
        lineWrapping: false,
        extraKeys: {
          'Ctrl-Space': 'autocomplete',
          'Ctrl-/': 'toggleComment',
          'Cmd-/': 'toggleComment',
          'Ctrl-Enter': () => run(),
          'Cmd-Enter': () => run(),
          Tab: (editor) => (editor.somethingSelected() ? editor.indentSelection('add')
            : editor.replaceSelection(' '.repeat(editor.getOption('indentUnit')), 'end')),
          'Shift-Tab': (editor) => editor.indentSelection('subtract'),
        },
        hintOptions: {hint: (editor) => hintsFor(editor, language()), completeSingle: false},
      });
      window.codeEditor = cm;
      textarea.required = false; // yashirin textarea brauzer tekshiruvini to'sib qo'ymasin
      const wrapper = cm.getWrapperElement();
      const applyFont = () => { wrapper.style.fontSize = `${fontSize}px`; cm.refresh(); };
      applyFont();
      document.getElementById('ideFontPlus').addEventListener('click', () => {
        fontSize = Math.min(fontSize + 1, 24); localStorage.setItem('ide-font', fontSize); applyFont();
      });
      document.getElementById('ideFontMinus').addEventListener('click', () => {
        fontSize = Math.max(fontSize - 1, 11); localStorage.setItem('ide-font', fontSize); applyFont();
      });
      cm.on('change', () => { cm.save(); lastTyped = Date.now(); saveDraft(); });
      cm.on('cursorActivity', () => {
        const pos = cm.getCursor();
        document.getElementById('ideCursor').textContent = `Qator ${pos.line + 1}, ustun ${pos.ch + 1}`;
      });
      // Harf yozilganda maslahatlar o'zi chiqadi.
      cm.on('inputRead', (editor, change) => {
        if (editor.state.completionActive || change.origin !== '+input') return;
        const typed = change.text[change.text.length - 1];
        if (change.text.length === 1 && /^[\w.#]{1,3}$/.test(typed)) editor.showHint({completeSingle: false});
      });
    } else {
      textarea.addEventListener('input', () => { lastTyped = Date.now(); saveDraft(); });
    }

    function setLanguageUi() {
      fileLabel.textContent = language() === 'cpp' ? 'main.cpp' : 'main.py';
      if (cm) cm.setOption('mode', language() === 'cpp' ? 'text/x-c++src' : 'python');
    }
    languageSelect.addEventListener('change', setLanguageUi);
    setLanguageUi();

    document.getElementById('ideTemplate').addEventListener('click', () => {
      if (getCode().trim() && !confirm('Joriy kod shablon bilan almashtirilsinmi?')) return;
      const template = TEMPLATES[language()];
      if (cm) { cm.setValue(template); cm.focus(); } else { textarea.value = template; }
    });
    document.getElementById('ideSample').addEventListener('click', () => { stdin.value = options.sampleInput; });
    document.getElementById('codeForm').addEventListener('submit', () => { if (cm) cm.save(); });

    function show(text, cls) {
      const span = document.createElement('span');
      if (cls) span.className = cls;
      span.textContent = text;
      output.appendChild(span);
    }

    async function run() {
      if (runButton.disabled) return;
      if (!getCode().trim()) { output.textContent = 'Avval kod yozing.'; return; }
      runButton.disabled = true;
      runButton.textContent = '⏳ Ishlamoqda…';
      runStatus.textContent = '';
      runStatus.className = 'ide-run-status';
      output.textContent = '';
      show('Dastur ishga tushirilmoqda…', 'ide-muted');
      try {
        const response = await fetch(options.runUrl, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
          body: JSON.stringify({language: language(), source_code: getCode(), stdin: stdin.value}),
        });
        const data = response.headers.get('Content-Type')?.includes('json') ? await response.json() : null;
        output.textContent = '';
        if (!response.ok || !data || data.error) {
          show((data && data.error) || `Server xatosi (${response.status}).`, 'ide-err');
          if (data && data.finished) setTimeout(() => { window.allowContestLeave?.(); window.location.reload(); }, 1500);
          return;
        }
        const [label, kind] = STATUS[data.status] || [data.status, 'bad'];
        runStatus.textContent = data.status === 'compile_error' ? label : `${label} · ${data.time_ms} ms`;
        runStatus.classList.add(kind === 'ok' ? 'is-ok' : 'is-bad');
        data.stdout = (data.stdout || '').replace(/\r\n/g, '\n').replace(/\s+$/, '');
        if (data.stdout) show(data.stdout +(data.stdout_truncated ? '\n… (chiqish qisqartirildi)' : ''));
        else if (data.status === 'ok') show('(dastur hech narsa chiqarmadi)', 'ide-muted');
        if (data.stderr) show((data.stdout ? '\n' : '') + data.stderr, 'ide-err');
        if (data.status === 'ok' && options.sampleOutput && normalize(stdin.value) === normalize(options.sampleInput)) {
          const same = normalize(data.stdout) === normalize(options.sampleOutput);
          show(same ? '\n\n✓ Namuna javobiga mos keldi' : '\n\n✗ Namuna javobidan farq qiladi', same ? 'ide-ok' : 'ide-err');
        }
      } catch (error) {
        output.textContent = '';
        show('Server bilan aloqa uzildi. Qayta urinib ko‘ring.', 'ide-err');
      } finally {
        runButton.disabled = false;
        runButton.textContent = '▶ Ishga tushirish';
      }
    }
    runButton.addEventListener('click', run);

    return {
      idleFor: () => Date.now() - lastTyped,
      lock() {
        if (cm) cm.setOption('readOnly', 'nocursor');
        textarea.disabled = true;
        runButton.disabled = true;
        document.getElementById('ideSubmit').disabled = true;
      },
    };
  };
})();
