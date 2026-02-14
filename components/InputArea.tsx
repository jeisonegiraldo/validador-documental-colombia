import React, { useRef } from 'react';
import { Camera, Upload, FileText } from 'lucide-react';

interface InputAreaProps {
  onFileSelect: (file: File) => void;
  disabled: boolean;
  acceptTypes?: string;
}

export const InputArea: React.FC<InputAreaProps> = ({ onFileSelect, disabled, acceptTypes = "image/*,application/pdf" }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelect(e.target.files[0]);
    }
  };

  return (
    <div className="bg-white p-4 border-t border-gray-200 sticky bottom-0 w-full z-10 safe-pb">
      <input
        type="file"
        ref={fileInputRef}
        className="hidden"
        accept={acceptTypes}
        onChange={handleFileChange}
        disabled={disabled}
      />
      
      <div className="flex gap-2 justify-center">
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          className={`
            flex-1 flex items-center justify-center gap-2 py-3 px-6 rounded-full font-medium transition-all shadow-md
            ${disabled 
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
              : 'bg-[#00a884] text-white hover:bg-[#008f6f] active:scale-95'
            }
          `}
        >
          {disabled ? (
            <span>Procesando...</span>
          ) : (
            <>
              <Camera className="w-5 h-5" />
              <span>Adjuntar Foto o PDF</span>
            </>
          )}
        </button>
      </div>
      <div className="text-center mt-2 text-xs text-gray-500">
        Aceptamos fotos (JPG, PNG) y documentos PDF
      </div>
    </div>
  );
};
