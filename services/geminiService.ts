import { GoogleGenAI, Type } from "@google/genai";
import { ValidationResult, DocumentSide } from "../types";
import { fileToBase64 } from "../utils/fileHelpers";

// Initialize Gemini Client
// NOTE: API Key is expected to be in process.env.API_KEY
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

const MODEL_NAME = 'gemini-3-pro-preview';

const validationSchema = {
  type: Type.OBJECT,
  properties: {
    isValidColombianID: {
      type: Type.BOOLEAN,
      description: "True if the document is a Colombian Cédula de Ciudadanía or Tarjeta de Identidad.",
    },
    isLegible: {
      type: Type.BOOLEAN,
      description: "True if the text and photo are clear, not blurry, and not too dark.",
    },
    documentSide: {
      type: Type.STRING,
      enum: ["front", "back", "full_document", "unknown"],
      description: "The side of the ID detected. 'full_document' if it contains both sides or is a copy.",
    },
    userFeedback: {
      type: Type.STRING,
      description: "Polite, helpful feedback in Spanish for a rural user. Explain if it's blurry, dark, or the wrong side.",
    },
  },
  required: ["isValidColombianID", "isLegible", "documentSide", "userFeedback"],
};

export const validateDocument = async (file: File, expectedSide?: DocumentSide): Promise<ValidationResult> => {
  try {
    const base64Data = await fileToBase64(file);
    const mimeType = file.type;

    const prompt = `
      Actúa como un validador experto de documentos de identidad colombianos (Cédula de Ciudadanía o Tarjeta de Identidad) para un proceso de reclamación de víctimas.
      
      Analiza el archivo adjunto.
      1. Verifica si es un documento de identidad colombiano válido.
      2. Determina si es la cara FRONTAL (donde suele estar la foto), la cara TRASERA (donde está la huella/datos de nacimiento), o un documento COMPLETO (ambas caras).
      3. Verifica rigurosamente la legibilidad:
         - ¿Está borrosa?
         - ¿Está muy oscura o con brillos que tapan el texto?
         - ¿Los datos son legibles?
      
      ${expectedSide ? `NOTA: Se espera que esta sea la cara: ${expectedSide === DocumentSide.FRONT ? 'FRONTAL' : 'TRASERA'}.` : ''}

      Responde en formato JSON.
      El campo 'userFeedback' debe ser un mensaje amable, en español sencillo, dirigido al usuario. 
      - Si está bien: "La foto se ve muy bien."
      - Si está borrosa: "La imagen está un poco borrosa. Por favor intenta tomarla de nuevo asegurando que el texto se lea bien."
      - Si es el lado incorrecto: "Esta parece ser la otra cara. Por favor envía la cara solicitada."
    `;

    const response = await ai.models.generateContent({
      model: MODEL_NAME,
      contents: {
        parts: [
          {
            inlineData: {
              mimeType: mimeType,
              data: base64Data
            }
          },
          { text: prompt }
        ]
      },
      config: {
        responseMimeType: "application/json",
        responseSchema: validationSchema,
        thinkingConfig: { thinkingBudget: 2048 }, // Using some thinking budget for accurate image analysis
      }
    });

    const jsonText = response.text || "{}";
    const result = JSON.parse(jsonText);

    // Map string response to Enum
    let detectedSide = DocumentSide.UNKNOWN;
    switch (result.documentSide) {
      case 'front': detectedSide = DocumentSide.FRONT; break;
      case 'back': detectedSide = DocumentSide.BACK; break;
      case 'full_document': detectedSide = DocumentSide.FULL; break;
      default: detectedSide = DocumentSide.UNKNOWN;
    }

    return {
      isValid: result.isValidColombianID === true,
      isLegible: result.isLegible === true,
      detectedSide: detectedSide,
      feedback: result.userFeedback || "No se pudo analizar el documento."
    };

  } catch (error) {
    console.error("Error validating document:", error);
    return {
      isValid: false,
      isLegible: false,
      detectedSide: DocumentSide.UNKNOWN,
      feedback: "Hubo un error técnico analizando la imagen. Por favor intenta nuevamente."
    };
  }
};
