import { jsPDF } from "jspdf";
import { fileToBase64 } from "../utils/fileHelpers";

export const generateCombinedPdf = async (frontFile: File, backFile: File): Promise<Blob> => {
  const doc = new jsPDF();
  
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 20;
  
  // Calculate dimensions to fit 2 images on one page
  // A standard ID card ratio is roughly 85.60 × 53.98 mm (~1.58 aspect ratio)
  // We want them large enough to be readable.
  
  const imgWidth = pageWidth - (margin * 2);
  const imgHeight = imgWidth * 0.65; // Approx ID card ratio scaled
  
  // Load images
  const frontBase64 = await fileToBase64(frontFile);
  const backBase64 = await fileToBase64(backFile);
  
  const frontFormat = frontFile.type.includes('png') ? 'PNG' : 'JPEG';
  const backFormat = backFile.type.includes('png') ? 'PNG' : 'JPEG';

  // Add Title
  doc.setFontSize(16);
  doc.text("Documento de Identidad Consolidado", pageWidth / 2, margin, { align: "center" });
  doc.setFontSize(10);
  doc.text(`Generado: ${new Date().toLocaleDateString()}`, pageWidth / 2, margin + 7, { align: "center" });

  // Add Front
  doc.text("Cara Frontal:", margin, margin + 20);
  doc.addImage(frontBase64, frontFormat, margin, margin + 25, imgWidth, imgHeight);

  // Add Back
  const secondImageY = margin + 25 + imgHeight + 20;
  doc.text("Cara Trasera:", margin, secondImageY - 5);
  doc.addImage(backBase64, backFormat, margin, secondImageY, imgWidth, imgHeight);

  return doc.output('blob');
};
