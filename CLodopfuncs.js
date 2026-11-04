/*
 * CLodopfuncs.js —— 自研兼容桩 v2（clean-room，不含任何 LODOP 官方代码）
 *
 * API 面已对照官方安装包内提取的 CLodopfuncs.js（74 个方法）补齐：
 *  - 全部 74 个方法名都可用（未实现的自动记录 warning，不会报错中断页面）
 *  - A 系列变体（ADD_PRINT_TEXTA 等）、NEWPAGE、SET_LICENSES、
 *    SEND_PRINT_RAWDATA（原始 TSPL/ZPL 直发）、GET_PRINTER_COUNT/NAME
 *
 * 原理：把网页调用的 LODOP 命令按顺序收集成任务 JSON，提交给本机
 * Python 打印服务（与本脚本同源），由 Python 渲染位图送 Windows 驱动。
 */
(function () {
    if (window.CLODOP) return;                 // 双端口同时加载时，先到先得

    var BASE = "";
    try {
        if (document.currentScript && document.currentScript.src)
            BASE = document.currentScript.src.replace(/CLodopfuncs\.js.*$/, "");
    } catch (e) { BASE = "http://localhost:8000/"; }

    function newJob() {
        return { task: "default", pagesize: null, modes: {}, copies: 1, printer: null, items: [], raw_data: null };
    }
    var job = newJob();

    function last() { return job.items.length ? job.items[job.items.length - 1] : null; }
    function add(op, args) {
        var it = { op: op, args: Array.prototype.slice.call(args), styles: {} };
        job.items.push(it);
        return it;
    }
    function styleAt(idx, k, v) {              // 0/-1=最后一个，>0=第 idx 个
        var it = (idx > 0 && job.items[idx - 1]) ? job.items[idx - 1] : last();
        if (it) it.styles[String(k)] = v;
    }

    function post(path, payload) {
        var xhr = new XMLHttpRequest();
        xhr.open("POST", BASE + path, false);  // 同步，贴近 LODOP 的调用时序
        xhr.setRequestHeader("Content-Type", "application/json;charset=utf-8");
        try { xhr.send(JSON.stringify(payload)); }
        catch (e) { alert("打印服务未启动: " + e); return null; }
        if (xhr.status !== 200) { alert("打印服务返回 " + xhr.status + ": " + xhr.responseText); return null; }
        try { return JSON.parse(xhr.responseText); } catch (e) { return {}; }
    }

    function submit(print) {
        var resp = post(print ? "clodop/print" : "clodop/render", job);
        job = newJob();                        // 提交后复位
        if (!resp) return false;
        if (print) {
            if (!resp.ok) alert("打印失败: " + (resp.error || "未知错误"));
            else if (resp.message) console.log("[CLodop-python] " + resp.message);
            if (resp.warnings && resp.warnings.length) console.warn("[CLodop-python]", resp.warnings);
            return !!resp.ok;
        }
        if (resp.id) { window.open(BASE + "preview/" + resp.id, "_blank"); return true; }
        alert("预览失败: " + (resp.error || ""));
        return false;
    }

    function getPrinters() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", BASE + "clodop/printers", false);
        try { xhr.send(); } catch (e) { return []; }
        try { return JSON.parse(xhr.responseText).printers || []; } catch (e) { return []; }
    }

    var base = {
        CVERSION: "6.5.9.8",
        VERSION: "6.226",
        PRIORITY: 1,

        /* ---- 任务 ---- */
        PRINT_INIT: function (t) { job = newJob(); job.task = t || "default"; },
        PRINT_INITA: function (t, l, w, h, task) { job = newJob(); job.task = task || "default"; },
        SET_PRINT_PAGESIZE: function (o, w, h, name) { job.pagesize = { orient: o, w: w, h: h, name: name }; },
        SET_PRINT_MODE: function (k, v) { job.modes[String(k)] = v; },
        SET_PRINT_COPIES: function (n) { job.copies = parseInt(n) || 1; },
        SET_PRINTER_INDEXA: function (i) { job.printer = i; },
        SET_PRINTER_INDEX: function (i) { job.printer = i; },
        SET_LICENSES: function () { },
        NEWPAGE: function () { add("NEWPAGE", []); },
        NEWPAGEA: function () { add("NEWPAGE", []); },

        /* ---- 对象 ---- */
        ADD_PRINT_TEXT: function (t, l, w, h, txt) { add("ADD_PRINT_TEXT", [t, l, w, h, txt == null ? "" : String(txt)]); },
        ADD_PRINT_BARCODE: function (t, l, w, h, type, val) { add("ADD_PRINT_BARCODE", [t, l, w, h, String(type), String(val)]); },
        ADD_PRINT_IMAGE: function (t, l, w, h, src) { add("ADD_PRINT_IMAGE", [t, l, w, h, String(src)]); },
        ADD_PRINT_RECT: function (t, l, w, h, lw) { add("ADD_PRINT_RECT", [t, l, w, h, lw || 1]); },
        ADD_PRINT_ELLIPSE: function (t, l, w, h, s, lw) { add("ADD_PRINT_ELLIPSE", [t, l, w, h, s || 0, lw || 1]); },
        ADD_PRINT_LINE: function (t1, l1, t2, l2, lw) { add("ADD_PRINT_LINE", [t1, l1, t2, l2, lw || 1]); },
        ADD_PRINT_DNLINE: function (t1, l1, t2, l2, lw) { add("ADD_PRINT_LINE", [t1, l1, t2, l2, lw || 1]); },
        ADD_PRINT_UPLINE: function (t1, l1, t2, l2, lw) { add("ADD_PRINT_LINE", [t1, l1, t2, l2, lw || 1]); },
        ADD_PRINT_HTM: function () { add("ADD_PRINT_HTM", Array.prototype.slice.call(arguments)); },
        ADD_PRINT_TABLE: function () { add("ADD_PRINT_TABLE", Array.prototype.slice.call(arguments)); },

        /* ---- 样式 ---- */
        SET_PRINT_STYLE: function (k, v) { styleAt(0, k, v); },
        SET_PRINT_STYLEA: function (idx, k, v) { styleAt(idx, k, v); },

        /* ---- 动作 ---- */
        PRINT: function () { return submit(true); },
        PRINTA: function () { return submit(true); },
        PRINTB: function () { return submit(true); },
        PREVIEW: function () { return submit(false); },
        PREVIEWA: function () { return submit(false); },
        PREVIEWB: function () { return submit(false); },
        PRINT_DESIGN: function () { alert("PRINT_DESIGN（设计器）暂不支持"); },

        /* ---- 查询/系统 ---- */
        GET_PRINTER_COUNT: function () {
            var n = getPrinters().length;
            if (this.On_Return) { var t = Math.random(); this.TaskID = t; this.On_Return(t, n); }
            return n;
        },
        GET_PRINTER_NAME: function (i) {
            var ps = getPrinters(), v = (typeof i === "number") ? (ps[i] || "") : (ps.indexOf(i) >= 0 ? i : "");
            if (this.On_Return) { var t = Math.random(); this.TaskID = t; this.On_Return(t, v); }
            return v;
        },

        /* ---- 原始指令通道（TSPL/ZPL/ESC-POS 直发） ---- */
        SEND_PRINT_RAWDATA: function (data) {
            job.raw_data = data;
            return submit(true);
        },
        WRITE_PORT_DATA: function (data) { job.raw_data = data; return submit(true); }
    };

    /* ---- A 系列变体：第一个参数为对象序号，丢弃后调用基础版 ---- */
    ["TEXT", "BARCODE", "RECT", "ELLIPSE", "HTM", "TABLE", "HTML"].forEach(function (k) {
        base["ADD_PRINT_" + k + "A"] = function () {
            var a = Array.prototype.slice.call(arguments); a.shift();
            base["ADD_PRINT_" + k].apply(null, a);
        };
    });
    base.ADD_PRINT_SETUP_BKIMG = function (src) {
        add("ADD_PRINT_IMAGE", [0, 0, 0, 0, String(src)]);   // 背景图暂按整页图片处理
    };

    /* ---- 兜底：官方 74 个 API 里未显式实现的方法，记录后跳过，页面不崩 ---- */
    window.CLODOP = new Proxy(base, {
        get: function (o, prop) {
            if (prop in o) return o[prop];
            return function () {
                job.items.push({ op: "UNSUPPORTED:" + String(prop),
                                 args: Array.prototype.slice.call(arguments), styles: {} });
            };
        }
    });

    window.getCLodop = function () { return window.CLODOP; };
})();
