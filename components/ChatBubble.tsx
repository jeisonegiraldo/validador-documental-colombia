import React from 'react';
import { Message } from '../types';
import { FileText, Image as ImageIcon, AlertCircle } from 'lucide-react';

interface ChatBubbleProps {
  message: Message;
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({ message }) => {
  const isBot = message.sender === 'bot';

  return (
    <div className={`flex w-full mb-4 ${isBot ? 'justify-start' : 'justify-end'}`}>
      <div 
        className={`max-w-[85%] sm:max-w-[70%] p-4 rounded-2xl shadow-sm text-sm sm:text-base ${
          isBot 
            ? 'bg-white text-gray-800 rounded-tl-none border border-gray-100' 
            : 'bg-[#DCF8C6] text-gray-900 rounded-tr-none' // WhatsApp-like green
        } ${message.isError ? 'border-2 border-red-200 bg-red-50' : ''}`}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
        
        {message.attachment && (
          <div className="mt-3 bg-black/5 p-2 rounded-lg overflow-hidden">
            {message.attachment.type === 'image' ? (
              <img 
                src={message.attachment.url} 
                alt="Adjunto" 
                className="w-full h-auto rounded-md object-cover max-h-60" 
              />
            ) : (
              <div className="flex items-center gap-3 p-2">
                <FileText className="w-8 h-8 text-red-500" />
                <span className="font-medium truncate max-w-full text-xs">
                  {message.attachment.file.name}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
