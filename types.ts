export type Sender = 'bot' | 'user';

export interface Message {
  id: string;
  text: string;
  sender: Sender;
  attachment?: {
    type: 'image' | 'pdf';
    url: string; // Object URL or Base64
    file: File;
  };
  isError?: boolean;
}

export enum DocumentSide {
  FRONT = 'front',
  BACK = 'back',
  FULL = 'full_document', // E.g., a PDF with both or a photocopy
  UNKNOWN = 'unknown'
}

export interface ValidationResult {
  isValid: boolean;
  isLegible: boolean;
  detectedSide: DocumentSide;
  feedback: string;
}

export enum FlowState {
  AWAITING_FRONT_OR_PDF = 'AWAITING_FRONT_OR_PDF',
  ANALYZING_FIRST = 'ANALYZING_FIRST',
  AWAITING_BACK = 'AWAITING_BACK',
  ANALYZING_BACK = 'ANALYZING_BACK',
  COMPLETED = 'COMPLETED',
  ERROR = 'ERROR'
}
