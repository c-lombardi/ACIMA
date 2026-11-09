// acima-unit: editor.monaco
/** The Monaco adapter: the only unit allowed to import the vendor. */
import * as monaco from 'monaco-editor';

export class MonacoEditor {
  open(note: string): string {
    return monaco.editor.create(document.body, { value: note }).getValue();
  }
}
