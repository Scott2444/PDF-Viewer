'use client';

interface TextTranscriptProps {
  data: Array<{text: string, bbox: number[]}>; 
}

const TextTranscript = ({ data }: TextTranscriptProps) => {
  return (
    <div className="overflow-y-auto max-h-[600px]">
      {data.length > 0 ? (
        data.map((item, index) => (
          <div 
            key={index}
            className="p-2 hover:bg-gray-100 cursor-pointer"
          >
            {item.text}
          </div>
        ))
      ) : (
        <p className="text-gray-500">No text extracted yet.</p>
      )}
    </div>
  );
};

export default TextTranscript;