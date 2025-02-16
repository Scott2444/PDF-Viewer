'use client';

interface TextTranscriptProps {
  data: Array<{id: string, text: string, bbox: number[]}>;
  selectedId?: string | null;
  onTextClick?: (id: string) => void;
}

const TextTranscript = ({ data, selectedId, onTextClick }: TextTranscriptProps) => {
  return (
    <div className="overflow-y-auto max-h-[600px]">
      {data.map((item) => (
        <div 
          key={item.id}
          className={`p-2 hover:bg-gray-100 cursor-pointer ${item.id === selectedId ? 'bg-blue-100' : ''}`}
          onClick={() => onTextClick && onTextClick(item.id)}
        >
          {item.text}
        </div>
      ))}
    </div>
  );
};

export default TextTranscript;