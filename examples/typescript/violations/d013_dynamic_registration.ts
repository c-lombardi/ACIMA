// Deliberately broken: the host discovers components instead of naming them.

export const modules = import.meta.glob('../modules/*/impl/*.ts');
