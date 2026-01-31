"""
Sistema centralizado de mensagens de erro para o Discord.

Este módulo fornece mensagens padronizadas e amigáveis para coordenadores,
com versões técnicas para administradores quando necessário.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCategory(Enum):
    """Categorias de erro para classificação."""
    DATA = "data"                    # Dados incompletos ou inválidos
    CONNECTION = "connection"        # Problemas de conexão/API
    AUTHENTICATION = "auth"          # Problemas de autenticação
    CONFIGURATION = "config"         # Configuração ausente ou inválida
    SYSTEM = "system"                # Erros internos do sistema
    TIMEOUT = "timeout"              # Timeout de operações
    PERMISSION = "permission"        # Problemas de permissão
    NOT_FOUND = "not_found"          # Recurso não encontrado


class ErrorMessages:
    """Gerador de mensagens de erro padronizadas."""

    # Contato para suporte (pode ser configurado)
    SUPPORT_CONTACT = "equipe de Tecnologia"

    @staticmethod
    def _format_timestamp() -> str:
        """Retorna timestamp formatado."""
        return datetime.now().strftime("%d/%m/%Y às %H:%M")

    @classmethod
    def get_user_message(
        cls,
        category: ErrorCategory,
        project_name: str,
        details: Optional[str] = None,
        suggestions: Optional[list] = None
    ) -> str:
        """
        Gera mensagem amigável para coordenadores.

        Args:
            category: Categoria do erro
            project_name: Nome do projeto
            details: Detalhes adicionais (opcional)
            suggestions: Lista de sugestões (opcional)

        Returns:
            Mensagem formatada para Discord
        """
        messages = {
            ErrorCategory.DATA: cls._data_error_user(project_name, details, suggestions),
            ErrorCategory.CONNECTION: cls._connection_error_user(project_name, details),
            ErrorCategory.AUTHENTICATION: cls._auth_error_user(project_name),
            ErrorCategory.CONFIGURATION: cls._config_error_user(project_name, details),
            ErrorCategory.SYSTEM: cls._system_error_user(project_name),
            ErrorCategory.TIMEOUT: cls._timeout_error_user(project_name),
            ErrorCategory.PERMISSION: cls._permission_error_user(project_name, details),
            ErrorCategory.NOT_FOUND: cls._not_found_error_user(project_name, details),
        }
        return messages.get(category, cls._generic_error_user(project_name))

    @classmethod
    def get_admin_message(
        cls,
        category: ErrorCategory,
        project_name: str,
        project_id: str,
        channel_id: str,
        error_details: Optional[str] = None,
        stack_trace: Optional[str] = None
    ) -> str:
        """
        Gera mensagem técnica para administradores.

        Args:
            category: Categoria do erro
            project_name: Nome do projeto
            project_id: ID do projeto
            channel_id: ID do canal Discord
            error_details: Detalhes técnicos do erro
            stack_trace: Stack trace (opcional)

        Returns:
            Mensagem formatada para canal admin
        """
        timestamp = cls._format_timestamp()
        category_names = {
            ErrorCategory.DATA: "Dados Incompletos",
            ErrorCategory.CONNECTION: "Falha de Conexão",
            ErrorCategory.AUTHENTICATION: "Falha de Autenticação",
            ErrorCategory.CONFIGURATION: "Configuração Inválida",
            ErrorCategory.SYSTEM: "Erro de Sistema",
            ErrorCategory.TIMEOUT: "Timeout",
            ErrorCategory.PERMISSION: "Sem Permissão",
            ErrorCategory.NOT_FOUND: "Não Encontrado",
        }

        message = f"""🚨 **ERRO NO RELATÓRIO**

📋 **Projeto:** {project_name}
🆔 **ID:** {project_id}
📢 **Canal:** <#{channel_id}>
⏰ **Horário:** {timestamp}

🔴 **Tipo:** {category_names.get(category, 'Desconhecido')}
"""

        if error_details:
            # Limitar tamanho dos detalhes
            details_truncated = error_details[:500] + "..." if len(error_details) > 500 else error_details
            message += f"\n📝 **Detalhes:**\n```\n{details_truncated}\n```"

        if stack_trace:
            # Limitar tamanho do stack trace
            trace_truncated = stack_trace[:300] + "..." if len(stack_trace) > 300 else stack_trace
            message += f"\n🔍 **Trace:**\n```\n{trace_truncated}\n```"

        message += f"\n📁 **Logs:** Verificar `logs/report_system_{datetime.now().strftime('%Y-%m-%d')}.log`"

        return message

    # ==================== MENSAGENS PARA USUÁRIOS ====================

    @classmethod
    def _data_error_user(cls, project_name: str, details: Optional[str], suggestions: Optional[list]) -> str:
        """Erro de dados incompletos ou inválidos."""
        timestamp = cls._format_timestamp()

        # Sugestões padrão para erros de dados
        default_suggestions = [
            "Verifique se todas as linhas do cronograma têm **STATUS** preenchido",
            "Confirme que a coluna **DISCIPLINA** não tem células vazias",
            "Aguarde 5 minutos e tente novamente com `!relatorio`"
        ]

        sugg_list = suggestions or default_suggestions
        suggestions_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(sugg_list)])

        detail_text = f"\n\n📝 **Detalhe:** {details}" if details else ""

        return f"""❌ **Não foi possível gerar o relatório**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
Encontramos dados incompletos ou inválidos no cronograma.{detail_text}

✅ **O que você pode fazer:**
{suggestions_text}

💬 Se o problema persistir, contate a {cls.SUPPORT_CONTACT}."""

    @classmethod
    def _connection_error_user(cls, project_name: str, details: Optional[str]) -> str:
        """Erro de conexão com APIs externas."""
        timestamp = cls._format_timestamp()

        service = details or "um dos serviços externos"

        return f"""❌ **Problema de conexão**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
Não conseguimos conectar com {service}. Isso pode ser temporário.

✅ **O que você pode fazer:**
1. Aguarde 5-10 minutos
2. Tente novamente com `!relatorio`
3. Se continuar falhando, o problema pode estar no serviço externo

💬 Se persistir por mais de 30 minutos, contate a {cls.SUPPORT_CONTACT}."""

    @classmethod
    def _auth_error_user(cls, project_name: str) -> str:
        """Erro de autenticação."""
        timestamp = cls._format_timestamp()

        return f"""❌ **Problema de autenticação**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
As credenciais de acesso aos sistemas expiraram ou são inválidas.

⚠️ **Este problema precisa ser resolvido pela equipe técnica.**

💬 Por favor, contate a {cls.SUPPORT_CONTACT} informando:
• Nome do projeto
• Horário do erro
• Este canal"""

    @classmethod
    def _config_error_user(cls, project_name: str, details: Optional[str]) -> str:
        """Erro de configuração."""
        timestamp = cls._format_timestamp()

        config_detail = f"\n📝 **Detalhe:** {details}" if details else ""

        return f"""❌ **Configuração incompleta**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
Este projeto não está completamente configurado para gerar relatórios.{config_detail}

⚠️ **Este problema precisa ser resolvido pela equipe técnica.**

💬 Por favor, contate a {cls.SUPPORT_CONTACT} para configurar:
• ID do Construflow
• ID do Smartsheet
• Pasta do Google Drive"""

    @classmethod
    def _system_error_user(cls, project_name: str) -> str:
        """Erro interno do sistema."""
        timestamp = cls._format_timestamp()

        return f"""❌ **Erro no sistema**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
Ocorreu um erro interno durante o processamento do relatório.

✅ **O que você pode fazer:**
1. Aguarde alguns minutos
2. Tente novamente com `!relatorio`

💬 Se o erro se repetir, contate a {cls.SUPPORT_CONTACT} informando o horário exato do problema."""

    @classmethod
    def _timeout_error_user(cls, project_name: str) -> str:
        """Erro de timeout."""
        timestamp = cls._format_timestamp()

        return f"""⏱️ **Tempo esgotado**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
O processamento do relatório demorou mais que o esperado e foi interrompido.

✅ **O que você pode fazer:**
1. O sistema pode estar sobrecarregado - aguarde 10 minutos
2. Tente novamente com `!relatorio`
3. Se o projeto tiver muitos dados, pode precisar de mais tempo

💬 Se acontecer repetidamente, contate a {cls.SUPPORT_CONTACT}."""

    @classmethod
    def _permission_error_user(cls, project_name: str, details: Optional[str]) -> str:
        """Erro de permissão."""
        timestamp = cls._format_timestamp()

        resource = details or "um recurso necessário"

        return f"""🔒 **Sem permissão de acesso**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
O sistema não tem permissão para acessar {resource}.

⚠️ **Este problema precisa ser resolvido pela equipe técnica.**

💬 Por favor, contate a {cls.SUPPORT_CONTACT} para verificar as permissões."""

    @classmethod
    def _not_found_error_user(cls, project_name: str, details: Optional[str]) -> str:
        """Erro de recurso não encontrado."""
        timestamp = cls._format_timestamp()

        resource = details or "os dados do projeto"

        return f"""🔍 **Não encontrado**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
Não foi possível encontrar {resource}.

✅ **O que você pode fazer:**
1. Verifique se o projeto ainda está ativo no sistema
2. Confirme se o cronograma existe e não foi movido

💬 Se o projeto deveria existir, contate a {cls.SUPPORT_CONTACT}."""

    @classmethod
    def _generic_error_user(cls, project_name: str) -> str:
        """Erro genérico quando não há categoria específica."""
        timestamp = cls._format_timestamp()

        return f"""❌ **Erro ao gerar relatório**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

🔍 **O que aconteceu:**
Ocorreu um erro inesperado durante a geração do relatório.

✅ **O que você pode fazer:**
1. Aguarde alguns minutos
2. Tente novamente com `!relatorio`

💬 Se o problema persistir, contate a {cls.SUPPORT_CONTACT} informando o horário do erro."""

    # ==================== MENSAGENS DE SUCESSO ====================

    @classmethod
    def success_message(
        cls,
        project_name: str,
        report_url: Optional[str] = None,
        client_report: bool = True,
        team_report: bool = True
    ) -> str:
        """Mensagem de sucesso na geração do relatório."""
        timestamp = cls._format_timestamp()

        reports_generated = []
        if client_report:
            reports_generated.append("Cliente")
        if team_report:
            reports_generated.append("Equipe")

        reports_text = " e ".join(reports_generated)

        message = f"""✅ **Relatórios gerados com sucesso!**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}
📄 **Relatórios:** {reports_text}
"""

        if report_url:
            message += f"\n🔗 **Link:** {report_url}"

        return message

    @classmethod
    def partial_success_message(
        cls,
        project_name: str,
        generated: str,
        failed: str,
        reason: Optional[str] = None
    ) -> str:
        """Mensagem de sucesso parcial."""
        timestamp = cls._format_timestamp()

        reason_text = f"\n📝 **Motivo:** {reason}" if reason else ""

        return f"""⚠️ **Relatório gerado parcialmente**

📋 **Projeto:** {project_name}
⏰ **Horário:** {timestamp}

✅ **Gerado:** Relatório {generated}
❌ **Não gerado:** Relatório {failed}{reason_text}

💬 Se precisar do relatório completo, contate a {cls.SUPPORT_CONTACT}."""

    # ==================== MENSAGENS DE STATUS ====================

    @classmethod
    def processing_message(cls, project_name: str, step: Optional[str] = None) -> str:
        """Mensagem de processamento em andamento."""
        step_text = f"\n📍 **Etapa:** {step}" if step else ""

        return f"""🔄 **Gerando relatório...**

📋 **Projeto:** {project_name}{step_text}

⏳ Este processo pode levar alguns minutos. Você será notificado quando terminar."""

    @classmethod
    def queue_message(cls, project_name: str, position: int) -> str:
        """Mensagem de posição na fila."""
        if position == 0:
            return f"""🚀 **Iniciando geração do relatório**

📋 **Projeto:** {project_name}

⏳ O processamento começou. Você será notificado quando terminar."""

        return f"""📋 **Relatório adicionado à fila**

📋 **Projeto:** {project_name}
🔢 **Posição:** {position}º na fila

⏳ Você será notificado quando o processamento começar."""

    @classmethod
    def already_processing_message(cls, project_name: str, elapsed_minutes: int) -> str:
        """Mensagem quando já existe processamento em andamento."""
        return f"""⏳ **Processamento em andamento**

📋 **Projeto:** {project_name}
⏱️ **Tempo decorrido:** {elapsed_minutes} minutos

Já existe um relatório sendo gerado para este projeto.
Por favor, aguarde a conclusão."""

    @classmethod
    def already_queued_message(cls, project_name: str) -> str:
        """Mensagem quando projeto já está na fila."""
        return f"""⏳ **Já está na fila**

📋 **Projeto:** {project_name}

Já existe uma solicitação de relatório aguardando na fila.
Por favor, aguarde a conclusão."""


# ==================== FUNÇÕES AUXILIARES ====================

def classify_error(exception: Exception, context: Optional[str] = None) -> ErrorCategory:
    """
    Classifica uma exceção em uma categoria de erro.

    Args:
        exception: Exceção capturada
        context: Contexto adicional para classificação

    Returns:
        Categoria do erro
    """
    error_str = str(exception).lower()
    exception_type = type(exception).__name__.lower()

    # Mapeamento de palavras-chave para categorias
    keywords = {
        ErrorCategory.CONNECTION: [
            'connection', 'timeout', 'refused', 'network', 'unreachable',
            'dns', 'socket', 'ssl', 'https', 'http', 'api', 'request failed'
        ],
        ErrorCategory.AUTHENTICATION: [
            'auth', 'credential', 'token', 'expired', 'invalid key',
            'unauthorized', '401', '403', 'permission denied', 'access denied'
        ],
        ErrorCategory.PERMISSION: [
            'permission', 'forbidden', 'access', 'denied', 'not allowed'
        ],
        ErrorCategory.NOT_FOUND: [
            'not found', '404', 'does not exist', 'no such', 'missing'
        ],
        ErrorCategory.DATA: [
            'data', 'empty', 'invalid', 'null', 'none', 'nan',
            'column', 'row', 'field', 'value', 'format', 'parse'
        ],
        ErrorCategory.TIMEOUT: [
            'timeout', 'timed out', 'deadline', 'exceeded'
        ],
        ErrorCategory.CONFIGURATION: [
            'config', 'setting', 'environment', 'variable', 'not configured'
        ],
    }

    # Verificar palavras-chave
    for category, kw_list in keywords.items():
        for kw in kw_list:
            if kw in error_str or kw in exception_type:
                return category

    # Contexto adicional
    if context:
        context_lower = context.lower()
        if 'smartsheet' in context_lower or 'construflow' in context_lower:
            return ErrorCategory.DATA
        if 'drive' in context_lower or 'google' in context_lower:
            return ErrorCategory.PERMISSION

    # Padrão: erro de sistema
    return ErrorCategory.SYSTEM


def get_error_response(
    exception: Exception,
    project_name: str,
    project_id: str = "",
    channel_id: str = "",
    context: Optional[str] = None,
    include_admin: bool = True
) -> Dict[str, str]:
    """
    Gera resposta completa de erro (usuário + admin).

    Args:
        exception: Exceção capturada
        project_name: Nome do projeto
        project_id: ID do projeto
        channel_id: ID do canal Discord
        context: Contexto adicional
        include_admin: Se deve incluir mensagem para admin

    Returns:
        Dict com 'user' e opcionalmente 'admin'
    """
    import traceback

    category = classify_error(exception, context)

    response = {
        'user': ErrorMessages.get_user_message(
            category=category,
            project_name=project_name,
            details=context
        ),
        'category': category
    }

    if include_admin and project_id and channel_id:
        response['admin'] = ErrorMessages.get_admin_message(
            category=category,
            project_name=project_name,
            project_id=project_id,
            channel_id=channel_id,
            error_details=str(exception),
            stack_trace=traceback.format_exc()
        )

    return response
