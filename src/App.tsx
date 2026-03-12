import React, { useState, useEffect } from 'react';
import { Film, Clipboard, Loader, Sparkles, BookText, Image as ImageIcon, Settings, ChevronDown, ChevronUp, Terminal, Check, History, RefreshCw, FileText, Download, PlayCircle, Plus, Trash2, AlertCircle } from 'lucide-react';
import ApiConfig, { ApiConfigData } from './components/ApiConfig';

interface ProcessResult {
  ts: string;
  metadata: { title: string; description: string };
  script: string;
  audio_rel_path: string;
  frames: string[];
  xhs_copy?: string;
}

interface HistoryItem {
  ts: string;
  title: string;
  description: string;
  cover: string;
  script: string;
  xhs_copy: string;
  audio_rel_path: string;
  frames: string[];
}

type Status = 'idle' | 'fetching_media' | 'splitting_audio' | 'processing_asr' | 'analyzing_ai' | 'success' | 'error';

const Card: React.FC<{ title: string; icon: React.ReactNode; children: React.ReactNode; copyContent?: string; extraAction?: React.ReactNode }> = ({ title, icon, children, copyContent, extraAction }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!copyContent) return;
    navigator.clipboard.writeText(copyContent).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200/80 p-5 relative mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="font-semibold text-gray-800">{title}</h2>
        </div>
        <div className="flex items-center gap-2">
          {extraAction}
          {copyContent && (
            <button onClick={handleCopy} className={`transition-colors p-1 rounded ${copied ? 'text-green-600 bg-green-50' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'}`} title={copied ? "复制成功" : "复制内容"}>
              {copied ? <Check size={16} /> : <Clipboard size={16} />}
            </button>
          )}
        </div>
      </div>
      <div className="text-gray-700">{children}</div>
    </div>
  );
};

const ImagePreviewModal: React.FC<{ src: string; onClose: () => void }> = ({ src, onClose }) => (
  <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={onClose}>
    <img src={src} alt="全屏预览" className="max-w-[90vw] max-h-[90vh] object-contain" onClick={(e) => e.stopPropagation()} />
  </div>
);

const App: React.FC = () => {
  const [url, setUrl] = useState('');
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [status, setStatus] = useState<Status>('idle');
  const [logs, setLogs] = useState<string[]>([]);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [apiConfig, setApiConfig] = useState<ApiConfigData | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [editableScript, setEditableScript] = useState('');
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [deletingTs, setDeletingTs] = useState<string | null>(null);

  const fetchHistory = () => {
    fetch('http://localhost:8000/api/v1/history')
      .then(res => res.json())
      .then(data => setHistory(data))
      .catch(err => console.warn("无法加载历史记录:", err));
  };

  useEffect(() => {
    fetch('http://localhost:8000/api/get-config')
      .then(res => res.json())
      .then(data => { if (data.provider) setApiConfig(data); })
      .catch(err => console.warn("无法加载配置:", err));
    fetchHistory();
  }, []);

  useEffect(() => {
    if (result) {
        setEditableScript(result.script || "");
    }
  }, [result]);

  useEffect(() => {
    if (status === 'success' && url && result?.metadata.title && !url.includes(result.metadata.title)) {
        setStatus('idle');
    }
  }, [url, result, status]);

  const isProcessing = ['fetching_media', 'splitting_audio', 'processing_asr', 'analyzing_ai'].includes(status);

  const handleNewTask = () => {
    if (isProcessing) return;
    setResult(null);
    setStatus('idle');
    setLogs([]);
    setUrl('');
  };

  const handleSelectHistory = (item: HistoryItem) => {
    if (isProcessing) return;
    // 重置状态以触发重绘
    setResult(null);
    setLogs([]);

    setTimeout(() => {
        setResult({
            ts: item.ts,
            metadata: { title: item.title, description: item.description },
            script: item.script,
            audio_rel_path: item.audio_rel_path,
            frames: item.frames,
            xhs_copy: item.xhs_copy
        });
        setStatus('success');
    }, 0);
  };

  const handleDeleteHistory = async (ts: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (isProcessing) return;
    if (!window.confirm(`确定要删除任务 ${ts} 吗？此操作不可逆。`)) return;

    setDeletingTs(ts);
    try {
        const response = await fetch(`http://localhost:8000/api/v1/history/${ts}`, { method: 'DELETE' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail);
        }
        fetchHistory();
        if (result?.ts === ts) {
            handleNewTask();
        }
    } catch (error) {
        alert(`删除失败: ${error}`);
    } finally {
        setDeletingTs(null);
    }
  };

  const handleProcess = async () => {
    if (!url || !url.trim().startsWith('http')) {
      alert("请输入有效的视频链接");
      return;
    }
    if (!apiConfig?.apiKey) {
      alert('请先在设置中完成 API 配置');
      setIsConfigOpen(true);
      return;
    }

    setResult(null);
    setLogs([]);
    setStatus('fetching_media');
    setLogs(['[1/5] 正在初始化任务...']);

    try {
      const response = await fetch('http://localhost:8000/api/v1/stream-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) throw new Error(`HTTP Error ${response.status}`);

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const msg = JSON.parse(line);

            if (msg.error) {
                console.error("Backend Error:", msg.error);
                throw new Error(msg.error);
            }

            if (msg.step === 'splitting_audio') setStatus('splitting_audio');
            if (msg.step === 'asr_processing') setStatus('processing_asr');
            if (msg.step === 'analyzing') setStatus('analyzing_ai');
            if (msg.message) setLogs(prev => [...prev.slice(-5), msg.message]);

            if (msg.step === 'done') {
              if (!msg.data.script && (!msg.data.frames || msg.data.frames.length === 0)) {
                  throw new Error("提取失败：未获取到有效的视频素材");
              }
              setStatus('success');
              setResult(msg.data);
              setLogs([]);
              fetchHistory();
            }
          } catch (e) {
              if (e instanceof Error) throw e;
              console.warn('Parse error:', e);
          }
        }
      }
    } catch (error) {
      setStatus('error');
      setLogs(prev => [...prev, `❌ 错误: ${error instanceof Error ? error.message : '未知错误'}`]);
    }
  };

  const handleReSummarize = async (ts: string, customScript?: string) => {
    if (!apiConfig?.apiKey) {
      alert('请先在设置中完成 API 配置');
      setIsConfigOpen(true);
      return;
    }
    setIsGenerating(true);
    try {
      const response = await fetch('http://localhost:8000/api/v1/re-summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ts, custom_script: customScript }),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail);
      }
      const data: ProcessResult = await response.json();
      setResult(prev => prev ? { ...prev, xhs_copy: data.xhs_copy } : data);
      fetchHistory();
    } catch (error) {
      alert(`生成失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownloadScript = () => {
      const blob = new Blob([editableScript], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `script_${result?.ts || 'draft'}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
  };

  const handleDownloadImage = (imageUrl: string) => {
    const a = document.createElement('a');
    a.href = imageUrl;
    a.download = imageUrl.split('/').pop() || 'frame.jpg';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const getStatusText = () => {
    switch (status) {
      case 'fetching_media': return '解析中 (1/5)...';
      case 'splitting_audio': return '切分中 (2/5)...';
      case 'processing_asr': return '转写中 (3/5)...';
      case 'analyzing_ai': return '分析中 (4/5)...';
      case 'success': return '处理完成';
      case 'error': return '处理失败';
      default: return '开始提取';
    }
  };

  // 全局唯一 Key，用于强制重绘整个主内容区
  const globalKey = `${result?.ts || 'init'}-${status}`;

  return (
    // 1. 物理屏蔽：translate="no" 阻止翻译插件干扰
    <div className="flex min-h-screen bg-gray-50" translate="no">
      <aside className="w-72 bg-white border-r border-gray-200 p-4 space-y-3 flex-shrink-0 h-screen sticky top-0 overflow-hidden flex flex-col">
        <div className="flex items-center justify-between flex-shrink-0">
            <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2"><History size={18}/> 历史记录</h2>
            <button
                onClick={handleNewTask}
                disabled={isProcessing}
                className={`flex items-center gap-1 text-sm p-1 rounded-md bg-blue-50 transition-colors px-2 py-1 ${isProcessing ? 'text-gray-400 cursor-not-allowed opacity-50' : 'text-blue-600 hover:text-blue-800 hover:bg-blue-100'}`}
            >
                <Plus size={14}/> 新建
            </button>
        </div>
        <div className="space-y-2 overflow-y-auto flex-grow pr-1">
          {history.map(item => (
            <div key={item.ts} className={`group relative w-full text-left p-2 rounded-md transition-colors ${result?.ts === item.ts ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-100'} ${isProcessing ? 'opacity-50 cursor-not-allowed pointer-events-none' : ''}`}>
                <button onClick={() => handleSelectHistory(item)} className="w-full">
                    <div className="flex items-center gap-3">
                        {item.cover ?
                        <img src={item.cover} alt={item.title} className="w-16 h-10 object-cover rounded-md flex-shrink-0" /> :
                        <div className="w-16 h-10 bg-gray-200 rounded-md flex-shrink-0" />
                        }
                        <div className="flex-grow overflow-hidden text-left">
                        <p className="text-sm font-medium text-gray-800 truncate" title={item.title}>{item.title}</p>
                        <p className="text-xs text-gray-500">{item.ts}</p>
                        </div>
                    </div>
                </button>
                <button
                    onClick={(e) => handleDeleteHistory(item.ts, e)}
                    disabled={deletingTs === item.ts || isProcessing}
                    className="absolute top-1 right-1 p-1.5 rounded-md bg-white/80 text-gray-400 hover:bg-red-100 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity shadow-sm disabled:cursor-not-allowed"
                >
                    {deletingTs === item.ts ? <Loader size={14} className="animate-spin" /> : <Trash2 size={14} />}
                </button>
            </div>
          ))}
        </div>
      </aside>

      <main className="flex-grow p-10 h-screen overflow-y-auto">
        <div className="w-full max-w-6xl mx-auto">
          <header className="flex items-center justify-center gap-3 mb-8">
            <Film className="text-gray-700" size={32} />
            <h1 className="text-3xl font-bold text-gray-800">抖音爆款提取工具 Pro</h1>
          </header>

          {/* 2. 动态区域顶层锁：Key 变化时销毁重建整个内容区 */}
          <div key={globalKey}>
              {/* 常驻顶部控制区 */}
              <div className="max-w-3xl mx-auto mb-8">
                  <div className="mb-6 bg-white rounded-lg shadow-sm border border-gray-200/80 overflow-hidden">
                    <button onClick={() => setIsConfigOpen(!isConfigOpen)} className="w-full flex items-center justify-between p-4 hover:bg-gray-50">
                      <div className="flex items-center gap-2 text-gray-700">
                        <Settings size={18} />
                        <span className="font-medium">API 设置</span>
                        {apiConfig?.apiKey ? <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">已配置</span> : <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">未配置</span>}
                      </div>
                      {isConfigOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </button>
                    {isConfigOpen && <div className="p-4 border-t"><ApiConfig onConfigChange={setApiConfig} /></div>}
                  </div>

                  <div className="relative mb-4">
                    <input type="text" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="粘贴抖音视频链接开始新任务..." className="w-full pl-4 pr-36 py-4 text-base border rounded-lg focus:ring-2 focus:ring-blue-500 shadow-sm disabled:bg-gray-50" disabled={status !== 'idle' && status !== 'success' && status !== 'error'} />
                    <button onClick={handleProcess} disabled={status !== 'idle' && status !== 'success' && status !== 'error' || !url} className="absolute right-2 top-1/2 -translate-y-1/2 bg-blue-600 text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-400 flex items-center gap-2">
                      {status !== 'idle' && status !== 'success' && status !== 'error' ? <Loader size={16} className="animate-spin" /> : null}
                      {getStatusText()}
                    </button>
                  </div>

                  {status !== 'idle' && status !== 'success' && logs.length > 0 && (
                    <div className="mb-8 p-4 bg-gray-800 text-white rounded-lg font-mono text-xs space-y-1 max-h-40 overflow-y-auto">
                      {logs.map((log, i) => <p key={i} className="whitespace-pre-wrap">{`> ${log}`}</p>)}
                    </div>
                  )}
              </div>

              {/* 结果区域 */}
              {result && result.frames && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-10">
                  <div className="space-y-6">
                     {result.audio_rel_path && (
                         <div className="bg-black rounded-lg overflow-hidden shadow-lg aspect-video">
                            <video
                                src={`http://localhost:8000/downloads/${result.audio_rel_path}`}
                                controls
                                className="w-full h-full"
                                preload="auto"
                            />
                         </div>
                     )}

                     <div key={`${result.ts}-script-editor`}>
                        <Card
                            title="转录脚本 (可编辑)"
                            icon={<FileText size={18} />}
                            copyContent={editableScript}
                            extraAction={
                                <button onClick={handleDownloadScript} className="text-gray-400 hover:text-gray-600 p-1" title="下载脚本">
                                    <Download size={16} />
                                </button>
                            }
                        >
                            <textarea
                                value={editableScript}
                                onChange={(e) => setEditableScript(e.target.value)}
                                className="w-full h-96 p-3 text-sm text-gray-700 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 font-mono resize-y"
                            />
                            <button
                                onClick={() => handleReSummarize(result.ts, editableScript)}
                                disabled={isGenerating}
                                className="mt-3 w-full bg-blue-100 text-blue-700 py-2 rounded-md font-medium hover:bg-blue-200 flex items-center justify-center gap-2"
                            >
                                {isGenerating ? <Loader size={16} className="animate-spin" /> : <Sparkles size={16} />}
                                基于当前脚本生成/更新文案
                            </button>
                        </Card>
                     </div>
                  </div>

                  <div className="space-y-6">
                    {result.frames.length > 0 && (
                        <Card title="关键帧预览" icon={<ImageIcon size={18} />}>
                            <p className="text-xs text-gray-400 mb-3 -mt-2">💡 提示：点击图片可查看原图，右键“图片另存为”可下载。</p>
                            <div className="grid grid-cols-3 gap-3">
                                {result.frames.map((path, i) => (
                                    <div
                                        key={`${result.ts}-frame-${i}`}
                                        className="group relative aspect-video bg-gray-100 rounded-lg overflow-hidden border cursor-pointer hover:shadow-md transition-shadow"
                                        onClick={() => setPreviewImage(path)}
                                    >
                                        <img src={path} alt={`Frame ${i}`} className="w-full h-full object-cover"/>
                                    </div>
                                ))}
                            </div>
                        </Card>
                    )}
                    
                    <div key={`${result.ts}-xhs-copy`}>
                        <Card 
                            title="AI 爆款文案生成" 
                            icon={<Sparkles size={18} className="text-purple-600" />} 
                            copyContent={result.xhs_copy ?? ""}
                        >
                            {isGenerating ? (
                                <div className="flex items-center justify-center h-[300px] text-gray-400">
                                    <Loader className="animate-spin mr-2" /> 正在生成...
                                </div>
                            ) : (
                                <div className="prose prose-sm max-w-none whitespace-pre-wrap leading-relaxed text-gray-800 bg-purple-50/50 p-4 rounded-md border-purple-100 min-h-[300px] max-h-[600px] overflow-y-auto">
                                    {result.xhs_copy || "暂无生成记录，请点击左侧按钮生成。"}
                                </div>
                            )}
                        </Card>
                    </div>
                  </div>
                </div>
              )}
          </div>
        </div>
      </main>
      
      {previewImage && <ImagePreviewModal src={previewImage} onClose={() => setPreviewImage(null)} />}
    </div>
  );
};

export default App;
