import React, { useState, useEffect } from 'react';
import { Loader, CheckCircle, AlertTriangle } from 'lucide-react';

// 定义配置状态的类型
export interface ApiConfigData {
  provider: 'gemini' | 'openai' | 'ppio';
  apiKey: string;
  proxyUrl: string;
}

interface ApiConfigProps {
  onConfigChange: (config: ApiConfigData) => void;
}

const ApiConfig: React.FC<ApiConfigProps> = ({ onConfigChange }) => {
  const [config, setConfig] = useState<ApiConfigData>({
    provider: 'gemini',
    apiKey: '',
    proxyUrl: '', // 默认允许为空
  });

  const [isLoading, setIsLoading] = useState(false);
  const [verificationStatus, setVerificationStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const savedConfig = localStorage.getItem('apiConfig');
    if (savedConfig) {
      const parsedConfig: ApiConfigData = JSON.parse(savedConfig);
      setConfig(parsedConfig);
      onConfigChange(parsedConfig);
    }
  }, [onConfigChange]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setConfig(prev => ({ ...prev, [name]: value }));
    setVerificationStatus('idle');
  };

  const handleVerify = async () => {
    setIsLoading(true);
    setVerificationStatus('idle');
    setErrorMessage('');

    try {
      const response = await fetch('http://localhost:8000/api/verify-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      const data = await response.json();

      if (response.ok) {
        setVerificationStatus('success');
        localStorage.setItem('apiConfig', JSON.stringify(config));
        onConfigChange(config);
        console.log('配置已保存:', config);
      } else {
        setVerificationStatus('error');
        setErrorMessage(data.detail || '发生未知错误');
      }
    } catch (error) {
      setVerificationStatus('error');
      if (error instanceof Error) {
        setErrorMessage(`前端请求失败: ${error.message}。请确保后端服务正在运行。`);
      } else {
        setErrorMessage('发生未知的前端请求错误。');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200/80 p-6 my-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">API 配置</h2>
      <div className="space-y-4">
        <div>
          <label htmlFor="provider" className="block text-sm font-medium text-gray-700 mb-1">
            API 厂商
          </label>
          <select
            id="provider"
            name="provider"
            value={config.provider}
            onChange={handleInputChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="gemini">Gemini</option>
            <option value="openai">OpenAI</option>
            <option value="ppio">PPIO</option>
          </select>
        </div>
        <div>
          <label htmlFor="apiKey" className="block text-sm font-medium text-gray-700 mb-1">
            API Key
          </label>
          <input
            type="password"
            id="apiKey"
            name="apiKey"
            value={config.apiKey}
            onChange={handleInputChange}
            placeholder="请输入您的 API Key"
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div>
          <label htmlFor="proxyUrl" className="block text-sm font-medium text-gray-700 mb-1">
            代理地址 (Proxy URL)
          </label>
          <input
            type="text"
            id="proxyUrl"
            name="proxyUrl"
            value={config.proxyUrl}
            onChange={handleInputChange}
            placeholder="例如: http://127.0.0.1:7890 (留空表示直连)"
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          />
          {/* 新增提示文案 */}
          <p className="mt-1 text-xs text-gray-500">
            国内 API (如 PPIO) 或直连环境请保持为空。若需访问海外 API (如 Gemini)，请填入本地代理地址。
          </p>
        </div>
        <div className="flex items-center justify-between pt-2">
          <button
            onClick={handleVerify}
            disabled={isLoading || !config.apiKey}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-300"
          >
            {isLoading ? (
              <>
                <Loader className="animate-spin -ml-1 mr-2 h-5 w-5" />
                验证中...
              </>
            ) : (
              '验证并保存配置'
            )}
          </button>
          <div className="h-6">
            {verificationStatus === 'success' && (
              <div className="flex items-center text-green-600">
                <CheckCircle className="h-5 w-5 mr-1" />
                <span className="text-sm font-medium">配置已生效</span>
              </div>
            )}
            {verificationStatus === 'error' && (
              <div className="flex items-center text-red-600" title={errorMessage}>
                <AlertTriangle className="h-5 w-5 mr-1" />
                <span className="text-sm font-medium">验证失败</span>
              </div>
            )}
          </div>
        </div>
        {verificationStatus === 'error' && errorMessage && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm text-red-700">{errorMessage}</p>
            </div>
        )}
      </div>
    </div>
  );
};

export default ApiConfig;
