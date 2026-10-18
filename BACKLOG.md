# Backlog — features adiadas

Este arquivo lista features que foram conscientemente adiadas durante o desenvolvimento da v1, com o contexto de quando/por que foram adiadas.

## Etapa de Admin (adiada em 2026-10-18)

Operações destrutivas que exigem camada de segurança adicional, agrupadas em uma etapa própria pós-v1. Inclui:
- DELETE de categoria macro (ADR-005 define macro como fixas — mas pode haver caso excepcional)
- Reset total do banco de dados
- Exportar dados em CSV
- Importar categorias customizadas em lote

### Por que foi adiada

Modo administrador exige autenticação, confirmação explícita, auditoria/log e testes de segurança — é uma etapa inteira sozinha. Pra v1, cada feature individual (como "deletar macro") teria custo desproporcional ao benefício. Agrupadas em uma etapa de Admin coesa, fazem mais sentido depois que o core do app estiver funcional.
