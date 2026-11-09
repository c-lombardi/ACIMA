// acima-unit: legacy.pdf
/** Violation L006: an adapter unit no externals entry declares, so it has no port. */
import { PDFDocument } from 'pdf-lib';

export const pageCount = (document: PDFDocument): number => document.getPageCount();
