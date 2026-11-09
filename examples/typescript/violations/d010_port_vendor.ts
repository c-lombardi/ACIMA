// acima-unit: editor.port
/** Violation D010: a port that leaks the vendor's shape. */
import type { IStandaloneCodeEditor } from 'monaco-editor';

/** The capability the application needs from a code editor. */
export interface EditorPort {
  open(note: string): IStandaloneCodeEditor;
}
