'use client';

interface TextTranscriptProps {
  data: Array<{id: string, text: string, bbox: number[]}>;  // Add id
  selectedId?: string | null;  // Change to selectedId
  onTextClick?: (id: string) => void;  // Change to id
}

const TextTranscript = ({ data, selectedId, onTextClick }: TextTranscriptProps) => {
  return (
    <div className="overflow-y-auto max-h-[600px]">
      {data.map((item) => (
        <div 
          key={item.id}  // Use id as key
          className={`p-2 hover:bg-gray-100 cursor-pointer ${item.id === selectedId ? 'bg-blue-100' : ''}`}
          onClick={() => onTextClick && onTextClick(item.id)}  // Pass id
        >
          {item.text}
        </div>
      ))}
    </div>
  );
};

export default TextTranscript;