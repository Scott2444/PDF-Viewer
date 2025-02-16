'use client';

import { useState } from 'react';
import PdfViewer from '@/components/PdfViewer';
import TextTranscript from '@/components/TextTranscript';

export default function Home() {
  const [pdfUrl, setPdfUrl] = useState<string>('');
  const [extractedData, setExtractedData] = useState<Array<{ text: string; bbox: number[]; page: number }>>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedText, setSelectedText] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pdfUrl) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/extract', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });
  
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to process PDF');
      }
  
      const data = await response.json();
      setExtractedData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTextClick = (text: string) => {
    setSelectedText(text === selectedText ? null : text);
  };

  return (
    <main className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">PDF Upload and Extract System</h1>
      
      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="url"
            value={pdfUrl}
            onChange={(e) => setPdfUrl(e.target.value)}
            placeholder="Enter PDF URL"
            className="flex-grow p-2 border rounded"
            required
          />
          <button 
            type="submit" 
            className="bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600 disabled:bg-gray-400"
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : 'Extract'}
          </button>
        </div>
      </form>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="border rounded p-4 min-h-[500px]">
          <h2 className="text-xl font-semibold mb-2">PDF Viewer</h2>
          {pdfUrl ? (
            <PdfViewer 
              url={pdfUrl} 
              extractedData={extractedData} 
              selectedText={selectedText}
            />
          ) : (
            <p className="text-gray-500">Enter a PDF URL above</p>
          )}
        </div>
        
        <div className="border rounded p-4 min-h-[500px]">
          <h2 className="text-xl font-semibold mb-2">Extracted Text</h2>
          <TextTranscript 
            data={extractedData}
            selectedText={selectedText}
            onTextClick={handleTextClick}
          />
        </div>
      </div>
    </main>
  );
}