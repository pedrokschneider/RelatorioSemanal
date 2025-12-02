"""
Gerador de relatórios em formato HTML para e-mail.
Gera dois tipos de relatório: um para clientes e outro para projetistas/time.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import base64
import io

from ..config import ConfigManager

logger = logging.getLogger("ReportSystem")

# Tentar importar Pillow para processamento de imagens
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Cache para a logo processada
_logo_cache = None


def _get_logo_base64() -> str:
    """
    Carrega e processa a logo do arquivo Logo.png, retornando em base64.
    Usa cache para evitar reprocessamento.
    
    Returns:
        String base64 da logo otimizada
    """
    global _logo_cache
    
    # Retornar do cache se já foi processada
    if _logo_cache is not None:
        return _logo_cache
    
    logo_path = os.path.join(os.getcwd(), "Logo.png")
    
    if not os.path.exists(logo_path):
        logger.warning(f"Arquivo Logo.png não encontrado em {logo_path}")
        return ""
    
    try:
        if PIL_AVAILABLE:
            # Processar a imagem com Pillow
            img = Image.open(logo_path)
            
            # Converter para RGB se necessário
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_image.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_image
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Redimensionar mantendo proporção (max 200x200)
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            
            # Salvar em buffer como JPEG otimizado
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='JPEG', quality=85, optimize=True)
            output_buffer.seek(0)
            
            # Converter para base64
            base64_content = base64.b64encode(output_buffer.read()).decode('utf-8')
            data_uri = f"data:image/jpeg;base64,{base64_content}"
        else:
            # Se Pillow não estiver disponível, ler o arquivo diretamente
            with open(logo_path, 'rb') as f:
                image_data = f.read()
                base64_content = base64.b64encode(image_data).decode('utf-8')
                data_uri = f"data:image/png;base64,{base64_content}"
        
        # Armazenar no cache
        _logo_cache = data_uri
        return _logo_cache
        
    except Exception as e:
        logger.error(f"Erro ao processar logo: {e}")
        return ""


class HTMLReportGenerator:
    """Gera relatórios HTML formatados para e-mail."""
    
    def __init__(self, config: ConfigManager):
        """
        Inicializa o gerador de relatórios HTML.
        
        Args:
            config: Instância do ConfigManager
        """
        self.config = config
        self.reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_client_report(self, data: Dict[str, Any], project_id: str = None,
                               project_image_base64: Optional[str] = None,
                               email_url_gant: Optional[str] = None,
                               email_url_disciplina: Optional[str] = None) -> str:
        """
        Gera relatório HTML para o cliente.
        
        Args:
            data: Dados processados do projeto
            project_id: ID do projeto (opcional)
            project_image_base64: Imagem do projeto em base64 (opcional)
            
        Returns:
            HTML do relatório
        """
        if data is None:
            logger.error("Dados do projeto são None")
            return ""
        
        project_name = data.get('project_name', 'Projeto')
        client_name = self._get_client_name(data, project_id)
        today = datetime.now().strftime("%d/%m/%Y")
        
        # Obter dados
        client_issues = self._get_client_issues(data)
        delays = self._get_delays_client(data)
        schedule = self._get_schedule_client(data)
        
        # Gerar seções HTML
        pendencias_html = self._generate_pendencias_section(client_issues, project_id)
        atrasos_html = self._generate_atrasos_client_section(delays)
        cronograma_html, _ = self._generate_cronograma_client_section(schedule, email_url_gant, email_url_disciplina)
        
        # Contagens para os badges
        count_pendencias = len(client_issues) if client_issues else 0
        count_atrasos = len(delays) if delays else 0
        count_cronograma = len(schedule) if schedule else 0
        
        html = self._generate_base_html(
            project_name=project_name,
            subtitle=client_name,
            date=today,
            greeting="Prezados,<br>Segue o status atualizado do projeto para esta semana.",
            sections=[
                {
                    'title': 'Pendências do Cliente',
                    'count': count_pendencias,
                    'color': '#dc2626' if count_pendencias > 0 else '#16a34a',
                    'content': pendencias_html,
                    'open': True
                },
                {
                    'title': 'Atrasos e Desvios',
                    'count': count_atrasos,
                    'color': '#dc2626' if count_atrasos > 0 else '#16a34a',
                    'content': atrasos_html,
                    'open': False
                },
                {
                    'title': 'Cronograma',
                    'count': count_cronograma,
                    'color': '#64748b',
                    'content': cronograma_html,
                    'open': False
                }
            ],
            show_dashboard_button=True,
            project_id=project_id,
            header_color='#0f172a',
            report_type="Relatório Cliente",
            project_image_base64=project_image_base64,
            email_url_gant=email_url_gant,
            email_url_disciplina=email_url_disciplina
        )
        
        return html
    
    def generate_team_report(self, data: Dict[str, Any], project_id: str = None,
                             project_image_base64: Optional[str] = None,
                             email_url_gant: Optional[str] = None,
                             email_url_disciplina: Optional[str] = None) -> str:
        """
        Gera relatório HTML para a equipe/projetistas.
        
        Args:
            data: Dados processados do projeto
            project_id: ID do projeto (opcional)
            project_image_base64: Imagem do projeto em base64 (opcional)
            
        Returns:
            HTML do relatório
        """
        if data is None:
            logger.error("Dados do projeto são None")
            return ""
        
        project_name = data.get('project_name', 'Projeto')
        client_name = self._get_client_name(data, project_id)
        today = datetime.now().strftime("%d/%m/%Y")
        
        # Obter dados
        completed = self._get_completed_tasks(data)
        delays = self._get_delays_team(data)
        schedule = self._get_schedule_team(data)
        
        # Gerar seções HTML
        concluidas_html = self._generate_concluidas_section(completed)
        atrasos_html = self._generate_atrasos_team_section(delays)
        cronograma_html, _ = self._generate_cronograma_team_section(schedule, email_url_gant, email_url_disciplina)
        
        # Contagens para os badges
        count_concluidas = sum(len(tasks) for tasks in completed.values()) if completed else 0
        count_atrasos = len(delays) if delays else 0
        count_cronograma = sum(len(tasks) for disc in schedule.values() for tasks in disc.values()) if schedule else 0
        
        html = self._generate_base_html(
            project_name=project_name,
            subtitle=client_name,
            date=today,
            greeting="Boa tarde, pessoal,<br>Segue o status do projeto para esta semana.",
            sections=[
                {
                    'title': 'Atividades Concluídas',
                    'count': count_concluidas,
                    'color': '#16a34a',
                    'content': concluidas_html,
                    'open': True
                },
                {
                    'title': 'Atrasos e Desvios',
                    'count': count_atrasos,
                    'color': '#dc2626' if count_atrasos > 0 else '#16a34a',
                    'content': atrasos_html,
                    'open': False
                },
                {
                    'title': 'Cronograma',
                    'count': count_cronograma,
                    'color': '#64748b',
                    'content': cronograma_html,
                    'open': False
                }
            ],
            project_image_base64=project_image_base64,
            show_dashboard_button=False,
            project_id=project_id,
            header_color='#1e293b',
            report_type="Relatório Projetistas",
            email_url_gant=email_url_gant,
            email_url_disciplina=email_url_disciplina
        )
        
        return html
    
    def _generate_base_html(self, project_name: str, subtitle: str, date: str,
                           greeting: str, sections: List[Dict], 
                           show_dashboard_button: bool, project_id: str,
                           header_color: str, report_type: str = "Relatório Cliente",
                           project_image_base64: Optional[str] = None,
                           email_url_gant: Optional[str] = None,
                           email_url_disciplina: Optional[str] = None) -> str:
        """Gera o HTML base do relatório no estilo Otus."""
        
        # Cores do padrão Otus
        otus_black = "#1a1a1a"
        otus_orange = "#f5a623"
        otus_gray_dark = "#2d2d2d"
        otus_gray_light = "#f5f5f5"
        otus_text = "#333333"
        otus_text_light = "#666666"
        
        # Gerar seções
        sections_html = ""
        for i, section in enumerate(sections):
            is_open = "open" if section.get('open', False) else ""
            # Usar laranja Otus para os badges
            badge_color = otus_orange if section['count'] > 0 else "#4ade80"
            
            sections_html += f'''
            <details {is_open} style="margin:0 0 12px;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;">
                <summary style="padding:16px 20px;cursor:pointer;font-family:'Montserrat',sans-serif;font-size:14px;font-weight:600;color:{otus_black};background:#fafafa;display:flex;align-items:center;gap:12px;">
                    <span style="flex:1;">{section['title']}</span>
                    <span style="display:inline-flex;align-items:center;justify-content:center;min-width:24px;height:24px;background:{badge_color};color:#ffffff;border-radius:6px;font-size:12px;font-weight:600;padding:0 8px;">{section['count']}</span>
                    <span class="chevron" style="color:#999;font-size:10px;">▼</span>
                </summary>
                <div style="padding:20px;background:#ffffff;font-family:'Source Sans Pro',sans-serif;">{section['content']}</div>
            </details>
            '''
        
        # Botão do dashboard (apenas para cliente)
        dashboard_button = ""
        if show_dashboard_button:
            dashboard_button = f'''
                    <tr>
                        <td style="padding:0 32px 32px;">
                            <a href="https://otus.datotecnologia.com.br/grupos" style="display:block;padding:14px 24px;background:{otus_orange};color:{otus_black};text-decoration:none;border-radius:8px;font-family:'Montserrat',sans-serif;font-size:13px;font-weight:600;text-align:center;">Acessar Dashboard de Indicadores</a>
                        </td>
                    </tr>
            '''
        
        construflow_url = f"https://app.construflow.com.br/workspace/project/{project_id}/issues" if project_id else "https://app.construflow.com.br"
        
        # Gerar todos os botões do rodapé na mesma linha usando tabela
        footer_buttons = '<table cellpadding="0" cellspacing="0" border="0" width="100%"><tr nowrap>'
        if email_url_gant:
            footer_buttons += f'<td nowrap style="padding-right:8px;vertical-align:middle;"><a href="{email_url_gant}" style="display:inline-block;padding:10px 16px;background:{otus_black};color:#ffffff;text-decoration:none;border-radius:6px;font-family:\'Montserrat\',sans-serif;font-size:12px;font-weight:600;white-space:nowrap;">Cronograma</a></td>'
        if email_url_disciplina:
            footer_buttons += f'<td nowrap style="padding-right:8px;vertical-align:middle;"><a href="{email_url_disciplina}" style="display:inline-block;padding:10px 16px;background:#ffffff;color:{otus_text};text-decoration:none;border-radius:6px;font-family:\'Montserrat\',sans-serif;font-size:12px;font-weight:600;border:1px solid #e0e0e0;white-space:nowrap;">Relatório Disciplinas</a></td>'
        footer_buttons += f'<td nowrap style="padding-right:8px;vertical-align:middle;"><a href="{construflow_url}" style="display:inline-block;padding:10px 16px;background:{otus_black};color:#ffffff;text-decoration:none;border-radius:6px;font-family:\'Montserrat\',sans-serif;font-size:12px;font-weight:600;white-space:nowrap;">Acessar Construflow</a></td>'
        footer_buttons += f'<td nowrap style="vertical-align:middle;"><a href="https://docs.google.com/forms/d/e/1FAIpQLSdc4k3NuH2Eu0GM7uBGJ2_Fq5iscxwG-99Sks6P5ho6AZyi0w/viewform" style="display:inline-block;padding:10px 16px;background:#ffffff;color:{otus_text};text-decoration:none;border-radius:6px;font-family:\'Montserrat\',sans-serif;font-size:12px;font-weight:600;border:1px solid #e0e0e0;white-space:nowrap;">Enviar Feedback</a></td>'
        footer_buttons += '</tr></table>'
        
        html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório - {project_name}</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Source+Sans+Pro:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; padding: 0; }}
        details summary::-webkit-details-marker {{ display: none; }}
        details summary {{ list-style: none; }}
        details[open] summary .chevron {{ transform: rotate(180deg); }}
        .chevron {{ transition: transform 0.2s ease; display: inline-block; }}
    </style>
</head>
<body style="margin:0;padding:0;background:{otus_gray_light};font-family:'Source Sans Pro',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:{otus_text};">
    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{otus_gray_light};">
        <tr>
            <td align="center" style="padding:40px 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:620px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- BARRA SUPERIOR BRANCA COM LOGO -->
                    <tr>
                        <td style="background:#ffffff;padding:20px 32px;border-bottom:3px solid {otus_orange};">
                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                <tr>
                                    <td style="vertical-align:middle;">
                                        <img src="{_get_logo_base64()}" alt="Otus" style="height:32px;width:auto;" />
                                    </td>
                                    <td align="right" style="vertical-align:middle;">
                                        <span style="font-family:'Source Sans Pro',sans-serif;font-size:12px;color:{otus_text_light};">{date}</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- HEADER HERO COM INFORMAÇÕES -->
                    <tr>
                        <td style="background:linear-gradient(135deg, {otus_black} 0%, #2d2d2d 100%);padding:32px;">
                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                <tr>
                                    <!-- Coluna Esquerda: Informações -->
                                    <td style="vertical-align:top;width:60%;">
                                        <!-- Cliente -->
                                        <p style="margin:0;font-family:'Source Sans Pro',sans-serif;font-size:10px;color:{otus_orange};text-transform:uppercase;letter-spacing:2px;font-weight:600;">Cliente</p>
                                        <p style="margin:4px 0 0;font-family:'Montserrat',sans-serif;font-size:28px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;line-height:1.1;">{subtitle}</p>
                                        
                                        <!-- Projeto -->
                                        <p style="margin:20px 0 0;font-family:'Source Sans Pro',sans-serif;font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:2px;">Projeto</p>
                                        <p style="margin:4px 0 0;font-family:'Montserrat',sans-serif;font-size:16px;font-weight:500;color:rgba(255,255,255,0.9);">{project_name}</p>
                                        
                                        <!-- Tipo de Relatório -->
                                        <table cellpadding="0" cellspacing="0" border="0" style="margin-top:20px;">
                                            <tr>
                                                <td style="background:{otus_orange};padding:8px 16px;border-radius:20px;">
                                                    <span style="font-family:'Montserrat',sans-serif;font-size:11px;font-weight:600;color:{otus_black};text-transform:uppercase;letter-spacing:0.5px;">{report_type}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                    <!-- Coluna Direita: Espaço para imagem -->
                                    <td style="vertical-align:middle;width:40%;text-align:right;">
                                        {self._get_project_image_html(project_image_base64, project_name)}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- SAUDAÇÃO -->
                    <tr>
                        <td style="padding:24px 40px;">
                            <p style="margin:0;font-family:'Source Sans Pro',sans-serif;font-size:15px;color:{otus_text};line-height:1.7;">{greeting}</p>
                        </td>
                    </tr>
                    
                    <!-- SEÇÕES -->
                    <tr>
                        <td style="padding:0 32px 32px;">
                            {sections_html}
                        </td>
                    </tr>
                    
                    {dashboard_button}
                    
                    <!-- ENCERRAMENTO -->
                    <tr>
                        <td style="padding:0 40px 32px;">
                            <p style="margin:0;font-family:'Source Sans Pro',sans-serif;font-size:14px;color:{otus_text_light};line-height:1.7;">Fico à disposição para esclarecimentos.</p>
                        </td>
                    </tr>
                    
                    <!-- RODAPÉ -->
                    <tr>
                        <td style="padding:20px 32px;background:{otus_gray_light};border-top:1px solid #e0e0e0;">
                            {footer_buttons}
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''
        
        return html
    
    def _get_client_name(self, data: Dict[str, Any], project_id: str) -> str:
        """Obtém o nome do cliente a partir dos dados do projeto."""
        # 1. Tentar obter do campo client_name nos dados
        client_name = data.get('client_name', '')
        if client_name and client_name != 'Cliente':
            return client_name
        
        # 2. Extrair do nome do projeto (formato: CLIENTE_PROJETO)
        project_name = data.get('project_name', '')
        if project_name and '_' in project_name:
            # Pegar a primeira parte antes do underscore como nome do cliente
            client_part = project_name.split('_')[0].strip()
            if client_part:
                return client_part
        
        # 3. Tentar obter do sistema como fallback
        try:
            import inspect
            import sys
            for name, obj in inspect.getmembers(sys.modules.get('__main__', {})):
                if hasattr(obj, 'get_client_names'):
                    names = obj.get_client_names(project_id)
                    if names and names[0]:
                        return names[0]
        except:
            pass
        
        # 4. Se não encontrar, usar o nome do projeto completo
        if project_name:
            return project_name
        
        return "Cliente"
    
    def _get_client_issues(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Obtém issues do cliente do Construflow.
        São as issues das disciplinas configuradas para o cliente com status 'todo'.
        """
        construflow_data = data.get('construflow_data', {})
        if not construflow_data:
            return []
        
        # Primeiro tentar usar client_issues já filtradas pelo DataProcessor
        client_issues = construflow_data.get('client_issues', [])
        
        if not client_issues:
            # Se não tiver client_issues, usar active_issues como fallback
            client_issues = construflow_data.get('active_issues', [])
            logger.info(f"Usando active_issues como fallback: {len(client_issues)} issues")
        
        # Filtrar apenas issues com status da disciplina = 'todo' (pendentes)
        # status_y = status da disciplina no Construflow
        todo_issues = []
        for issue in client_issues:
            status_disciplina = issue.get('status_y', '')
            if status_disciplina == 'todo':
                todo_issues.append(issue)
        
        logger.info(f"Issues do cliente com status 'todo': {len(todo_issues)} de {len(client_issues)}")
        return todo_issues
    
    def _get_completed_tasks(self, data: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Obtém tarefas concluídas agrupadas por disciplina.
        Para o relatório da equipe - mostra todas as disciplinas.
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            return {}
        
        all_tasks = smartsheet_data.get('all_tasks', [])
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        
        completed_by_discipline = {}
        for task in all_tasks:
            if not isinstance(task, dict):
                continue
            
            status = str(task.get('Status', '')).lower().strip()
            if status != 'feito':
                continue
            
            # Verificar se foi concluída na última semana (se tiver data)
            end_date_str = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
            if end_date_str:
                try:
                    end_date = self._parse_date(end_date_str)
                    if end_date and end_date < week_ago:
                        continue  # Ignorar tarefas concluídas há mais de uma semana
                except:
                    pass
            
            discipline = task.get('Disciplina', task.get('Discipline', 'Sem Disciplina')) or 'Sem Disciplina'
            if discipline not in completed_by_discipline:
                completed_by_discipline[discipline] = []
            completed_by_discipline[discipline].append(task)
        
        total_completed = sum(len(tasks) for tasks in completed_by_discipline.values())
        logger.info(f"Tarefas concluídas: {total_completed} em {len(completed_by_discipline)} disciplinas")
        return completed_by_discipline
    
    def _get_delays_client(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Obtém atrasos para relatório do cliente.
        Filtra tarefas atrasadas do SmartSheet onde Disciplina = 'Cliente'.
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            return []
        
        delayed_tasks = smartsheet_data.get('delayed_tasks', [])
        
        # Filtrar por disciplina "Cliente" (case-insensitive)
        client_delays = []
        for task in delayed_tasks:
            disciplina = str(task.get('Disciplina', task.get('Discipline', ''))).strip().lower()
            if disciplina == 'cliente':
                client_delays.append(task)
        
        logger.info(f"Atrasos do cliente: {len(client_delays)} de {len(delayed_tasks)} atrasadas")
        return client_delays
    
    def _get_delays_team(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Obtém atrasos para relatório da equipe.
        Retorna TODAS as tarefas atrasadas (todas as disciplinas).
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            return []
        
        delayed_tasks = smartsheet_data.get('delayed_tasks', [])
        logger.info(f"Atrasos da equipe: {len(delayed_tasks)} tarefas atrasadas")
        return delayed_tasks
    
    def _get_schedule_client(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Obtém cronograma para o cliente (entregas importantes).
        Filtra tarefas do SmartSheet onde Disciplina = 'Cliente' e que estão programadas.
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            return []
        
        all_tasks = smartsheet_data.get('all_tasks', [])
        today = datetime.now()
        future_cutoff = today + timedelta(days=30)
        
        # Filtrar tarefas do cliente que estão programadas (não concluídas)
        client_schedule = []
        for task in all_tasks:
            if not isinstance(task, dict):
                continue
            
            # Verificar disciplina
            disciplina = str(task.get('Disciplina', task.get('Discipline', ''))).strip().lower()
            if disciplina != 'cliente':
                continue
            
            # Verificar status (apenas tarefas não concluídas)
            status = str(task.get('Status', '')).lower().strip()
            if status == 'feito':
                continue
            
            # Verificar data
            task_date_str = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
            if not task_date_str:
                continue
            
            try:
                task_date = self._parse_date(task_date_str)
                if task_date and task_date >= today and task_date <= future_cutoff:
                    client_schedule.append(task)
            except:
                continue
        
        # Ordenar por data
        client_schedule.sort(key=lambda x: self._parse_date(x.get('Data Término', x.get('Data de Término', x.get('End Date', '')))) or datetime.max)
        
        logger.info(f"Cronograma do cliente: {len(client_schedule)} tarefas programadas")
        return client_schedule
    
    def _get_schedule_team(self, data: Dict[str, Any]) -> Dict[str, Dict[str, List]]:
        """Obtém cronograma detalhado para a equipe."""
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            return {}
        
        all_tasks = smartsheet_data.get('all_tasks', [])
        today = datetime.now()
        future_cutoff = today + timedelta(days=30)
        
        schedule = {}
        for task in all_tasks:
            if not isinstance(task, dict):
                continue
            
            # Verificar data
            task_date_str = task.get('Data Término', task.get('Data de Término', ''))
            if not task_date_str:
                continue
            
            try:
                task_date = self._parse_date(task_date_str)
                if not task_date or task_date < today or task_date > future_cutoff:
                    continue
            except:
                continue
            
            discipline = task.get('Disciplina', 'Sem Disciplina') or 'Sem Disciplina'
            status = str(task.get('Status', '')).lower().strip()
            
            if discipline not in schedule:
                schedule[discipline] = {'a_iniciar': [], 'programadas': []}
            
            if status == 'a fazer':
                schedule[discipline]['a_iniciar'].append(task)
            else:
                schedule[discipline]['programadas'].append(task)
        
        return schedule
    
    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse flexível de datas."""
        if not date_str:
            return None
        
        if hasattr(date_str, 'strftime'):
            return date_str
        
        if not isinstance(date_str, str):
            return None
        
        formats = ["%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d/%m"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue
        return None
    
    def _format_date(self, date_value) -> str:
        """Formata data para dd/mm."""
        if not date_value:
            return ""
        
        dt = self._parse_date(date_value)
        if dt:
            return dt.strftime("%d/%m")
        
        # Fallback
        return str(date_value)[:5]
    
    def _generate_pendencias_section(self, issues: List[Dict], project_id: str) -> str:
        """Gera HTML da seção de pendências do cliente - Design profissional Otus."""
        # Paleta profissional minimalista
        color_high = "#1a1a1a"      # Preto Otus para alta prioridade
        color_medium = "#666666"    # Cinza médio para média prioridade  
        color_low = "#999999"       # Cinza claro para baixa
        accent = "#f5a623"          # Laranja Otus apenas para destaques sutis
        
        if not issues:
            return '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#1a1a1a;">✓ Sem pendências do cliente nesta semana.</p>'
        
        # Agrupar por prioridade
        alta = []
        media = []
        baixa = []
        
        for issue in issues:
            priority = str(issue.get('priority', '')).lower()
            issue_data = {
                'code': issue.get('code', ''),
                'title': issue.get('title', 'Sem título'),
                'id': issue.get('id', '')
            }
            
            if priority in ['high', 'alta', '3']:
                alta.append(issue_data)
            elif priority in ['medium', 'media', 'média', '2']:
                media.append(issue_data)
            else:
                baixa.append(issue_data)
        
        html = ""
        
        # Prioridade Alta - destaque máximo
        if alta:
            html += '<div style="margin-bottom:24px;">'
            html += f'<p style="margin:0 0 12px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:{color_high};text-transform:uppercase;letter-spacing:1.5px;border-bottom:2px solid {color_high};padding-bottom:6px;display:inline-block;">Prioridade Alta</p>'
            html += '<div style="padding-left:0;">'
            for i, item in enumerate(alta, 1):
                url = f"https://app.construflow.com.br/workspace/project/{project_id}/issues?issueId={item['id']}"
                html += f'<p style="margin:0 0 10px;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#1a1a1a;line-height:1.7;padding:8px 12px;background:#f8f8f8;border-radius:4px;border-left:3px solid {accent};"><a href="{url}" style="color:#1a1a1a;text-decoration:none;font-weight:500;">{item["title"]}</a></p>'
            html += '</div></div>'
        
        # Prioridade Média
        if media:
            html += '<div style="margin-bottom:24px;">'
            html += f'<p style="margin:0 0 12px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:{color_medium};text-transform:uppercase;letter-spacing:1.5px;border-bottom:1px solid #ddd;padding-bottom:6px;display:inline-block;">Prioridade Média</p>'
            html += '<div style="padding-left:0;">'
            for i, item in enumerate(media, 1):
                url = f"https://app.construflow.com.br/workspace/project/{project_id}/issues?issueId={item['id']}"
                html += f'<p style="margin:0 0 8px;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#444;line-height:1.7;padding:6px 12px;border-left:2px solid #ddd;"><a href="{url}" style="color:#444;text-decoration:none;">{item["title"]}</a></p>'
            html += '</div></div>'
        
        # Prioridade Baixa
        if baixa:
            html += '<div style="margin-bottom:24px;">'
            html += f'<p style="margin:0 0 12px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:{color_low};text-transform:uppercase;letter-spacing:1.5px;">Prioridade Baixa</p>'
            html += '<div style="padding-left:0;">'
            for i, item in enumerate(baixa, 1):
                url = f"https://app.construflow.com.br/workspace/project/{project_id}/issues?issueId={item['id']}"
                html += f'<p style="margin:0 0 6px;font-family:\'Source Sans Pro\',sans-serif;font-size:13px;color:#666;line-height:1.6;padding-left:12px;"><a href="{url}" style="color:#666;text-decoration:none;">{item["title"]}</a></p>'
            html += '</div></div>'
        
        return html
    
    def _generate_concluidas_section(self, completed: Dict[str, List[Dict]]) -> str:
        """Gera HTML da seção de atividades concluídas - Design profissional Otus."""
        if not completed:
            return '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#666;">Nenhuma atividade concluída no período.</p>'
        
        html = ""
        for discipline, tasks in completed.items():
            html += f'<div style="margin-bottom:20px;"><p style="margin:0 0 10px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:#1a1a1a;text-transform:uppercase;letter-spacing:1.5px;border-bottom:1px solid #eee;padding-bottom:6px;">{discipline}</p>'
            
            for task in tasks:
                date = self._format_date(task.get('Data Término', task.get('Data de Término', '')))
                name = task.get('Nome da Tarefa', task.get('Task Name', ''))
                # Observação Otus
                observacao_otus = task.get('Observação Otus', task.get('Observacao Otus', ''))
                
                html += f'<div style="margin-bottom:8px;padding-left:12px;">'
                html += f'<p style="margin:0 0 4px;font-family:\'Source Sans Pro\',sans-serif;font-size:13px;color:#444;line-height:1.6;"><span style="font-family:\'Montserrat\',sans-serif;font-size:11px;color:#1a1a1a;font-weight:600;background:#f5f5f5;padding:2px 6px;border-radius:3px;margin-right:8px;">{date}</span>{name}</p>'
                
                if observacao_otus and str(observacao_otus).strip() and str(observacao_otus).lower() not in ['nan', 'none', '']:
                    html += f'<p style="margin:4px 0 0;font-family:\'Source Sans Pro\',sans-serif;font-size:12px;color:#f5a623;font-style:italic;padding-left:20px;"><span style="font-weight:600;color:#f5a623;">Observação Otus:</span> {observacao_otus}</p>'
                
                html += '</div>'
            
            html += '</div>'
        
        return html
    
    def _generate_atrasos_client_section(self, delays: List[Dict]) -> str:
        """Gera HTML da seção de atrasos para cliente - Design profissional Otus."""
        if not delays:
            return '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#1a1a1a;">✓ Nenhum atraso identificado no cronograma nesta semana.</p>'
        
        html = ""
        for task in delays:
            discipline = task.get('Disciplina', 'Sem Disciplina')
            name = task.get('Nome da Tarefa', task.get('Task Name', ''))
            
            # Data original (baseline) e nova data (replanejada)
            prev_date = self._format_date(task.get('Data de Fim - Reprogramado Otus', task.get('Baseline End', '')))
            new_date = self._format_date(task.get('Data Término', task.get('Data de Término', task.get('End Date', ''))))
            
            # Motivo de atraso
            motivo = task.get('Motivo de atraso', task.get('Delay Reason', ''))
            # Observação Otus
            observacao_otus = task.get('Observação Otus', task.get('Observacao Otus', ''))
            
            html += f'''
            <div style="margin-bottom:14px;padding:14px 16px;background:#fafafa;border-radius:4px;border-left:3px solid #1a1a1a;">
                <p style="margin:0;font-family:'Montserrat',sans-serif;font-size:10px;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:1px;">{discipline}</p>
                <p style="margin:6px 0 0;font-family:'Source Sans Pro',sans-serif;font-size:14px;color:#1a1a1a;font-weight:500;">{name}</p>
                <p style="margin:8px 0 0;font-family:'Source Sans Pro',sans-serif;font-size:12px;color:#666;">
                    <span style="text-decoration:line-through;color:#999;">{prev_date}</span>
                    <span style="margin:0 6px;color:#ccc;">→</span>
                    <span style="font-family:'Montserrat',sans-serif;font-weight:600;color:#1a1a1a;background:#f5a623;padding:2px 8px;border-radius:3px;">{new_date}</span>
                </p>'''
            
            if motivo and str(motivo).strip() and str(motivo).lower() not in ['nan', 'none', '']:
                html += f'''
                <p style="margin:8px 0 0;font-family:'Source Sans Pro',sans-serif;font-size:12px;color:#dc2626;font-style:italic;border-top:1px solid #eee;padding-top:8px;">
                    <span style="font-weight:600;color:#dc2626;">Motivo:</span> {motivo}
                </p>'''
            
            if observacao_otus and str(observacao_otus).strip() and str(observacao_otus).lower() not in ['nan', 'none', '']:
                html += f'''
                <p style="margin:8px 0 0;font-family:'Source Sans Pro',sans-serif;font-size:12px;color:#f5a623;font-style:italic;border-top:1px solid #eee;padding-top:8px;">
                    <span style="font-weight:600;color:#f5a623;">Observação Otus:</span> {observacao_otus}
                </p>'''
            
            html += '</div>'
        
        return html
    
    def _generate_atrasos_team_section(self, delays: List[Dict]) -> str:
        """Gera HTML da seção de atrasos para equipe - Design profissional Otus."""
        if not delays:
            return '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#1a1a1a;">✓ Nenhum atraso identificado no período.</p>'
        
        # Agrupar por disciplina
        by_discipline = {}
        for task in delays:
            discipline = task.get('Disciplina', 'Sem Disciplina')
            if discipline not in by_discipline:
                by_discipline[discipline] = []
            by_discipline[discipline].append(task)
        
        html = ""
        for discipline, tasks in by_discipline.items():
            # Só criar div da disciplina se houver tarefas
            if not tasks:
                continue
                
            html += f'<div style="margin-bottom:20px;"><p style="margin:0 0 12px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:#1a1a1a;text-transform:uppercase;letter-spacing:1.5px;border-bottom:1px solid #eee;padding-bottom:6px;">{discipline}</p>'
            
            for task in tasks:
                name = task.get('Nome da Tarefa', task.get('Task Name', ''))
                prev_date = self._format_date(task.get('Data de Fim - Reprogramado Otus', ''))
                new_date = self._format_date(task.get('Data Término', ''))
                motivo = task.get('Motivo de atraso', task.get('Delay Reason', ''))
                observacao_otus = task.get('Observação Otus', task.get('Observacao Otus', ''))
                
                html += f'''<div style="margin:0 0 14px;padding:12px 14px;background:#fafafa;border-radius:4px;border-left:3px solid #f5a623;">
                    <p style="margin:0;font-family:'Source Sans Pro',sans-serif;font-size:14px;color:#1a1a1a;font-weight:500;">{name}</p>
                    <p style="margin:6px 0 0;font-family:'Source Sans Pro',sans-serif;font-size:12px;color:#666;">
                        <span style="text-decoration:line-through;color:#999;">{prev_date}</span>
                        <span style="margin:0 6px;color:#ccc;">→</span>
                        <span style="font-family:'Montserrat',sans-serif;font-weight:600;color:#1a1a1a;background:#f5a623;padding:2px 8px;border-radius:3px;">{new_date}</span>
                    </p>'''
                
                if motivo and str(motivo).strip() and str(motivo).lower() not in ['nan', 'none', '']:
                    html += f'<p style="margin:8px 0 0;font-family:\'Source Sans Pro\',sans-serif;font-size:12px;color:#dc2626;font-style:italic;border-top:1px solid #eee;padding-top:8px;"><span style="font-weight:600;color:#dc2626;">Motivo:</span> {motivo}</p>'
                
                if observacao_otus and str(observacao_otus).strip() and str(observacao_otus).lower() not in ['nan', 'none', '']:
                    html += f'<p style="margin:8px 0 0;font-family:\'Source Sans Pro\',sans-serif;font-size:12px;color:#f5a623;font-style:italic;border-top:1px solid #eee;padding-top:8px;"><span style="font-weight:600;color:#f5a623;">Observação Otus:</span> {observacao_otus}</p>'
                
                html += '</div>'
            
            html += '</div>'
        
        return html
    
    def _generate_cronograma_client_section(self, schedule: List[Dict], 
                                            email_url_gant: Optional[str] = None,
                                            email_url_disciplina: Optional[str] = None) -> tuple:
        """Gera HTML da seção de cronograma para cliente - Design profissional Otus.
        
        Returns:
            Tupla (html_content, buttons_html) onde buttons_html pode ser vazio
        """
        if not schedule:
            html = '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#666;">Nenhuma atividade prevista para as próximas semanas.</p>'
        else:
            # Agrupar por disciplina
            by_discipline = {}
            for task in schedule:
                if not isinstance(task, dict):
                    continue
                discipline = task.get('Disciplina', 'Sem Disciplina')
                if discipline not in by_discipline:
                    by_discipline[discipline] = []
                by_discipline[discipline].append(task)
            
            html = ""
            for discipline, tasks in by_discipline.items():
                html += f'<div style="margin-bottom:20px;"><p style="margin:0 0 12px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:#1a1a1a;text-transform:uppercase;letter-spacing:1.5px;border-bottom:1px solid #eee;padding-bottom:6px;">{discipline}</p>'
                
                for task in tasks:
                    date = self._format_date(task.get('Data Término', task.get('Data de Término', '')))
                    name = task.get('Nome da Tarefa', task.get('Task Name', ''))
                    # Observação Otus
                    observacao_otus = task.get('Observação Otus', task.get('Observacao Otus', ''))
                    
                    html += f'<div style="margin-bottom:8px;padding-left:12px;">'
                    html += f'<p style="margin:0 0 4px;font-family:\'Source Sans Pro\',sans-serif;font-size:13px;color:#444;line-height:1.6;"><span style="font-family:\'Montserrat\',sans-serif;font-size:11px;color:#1a1a1a;font-weight:600;background:#f5f5f5;padding:2px 6px;border-radius:3px;margin-right:8px;">{date}</span>{name}</p>'
                    
                    if observacao_otus and str(observacao_otus).strip() and str(observacao_otus).lower() not in ['nan', 'none', '']:
                        html += f'<p style="margin:4px 0 0;font-family:\'Source Sans Pro\',sans-serif;font-size:12px;color:#f5a623;font-style:italic;padding-left:20px;"><span style="font-weight:600;color:#f5a623;">Observação Otus:</span> {observacao_otus}</p>'
                    
                    html += '</div>'
                
                html += '</div>'
        
        # Gerar botões separadamente - alinhados com os botões do rodapé
        buttons_html = ""
        if email_url_gant or email_url_disciplina:
            buttons_html = '<div style="margin-top:20px;padding:0;">'
            buttons_html += '<table cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td>'
            if email_url_gant:
                buttons_html += f'<a href="{email_url_gant}" style="display:inline-block;padding:10px 16px;background:#1a1a1a;color:#ffffff;text-decoration:none;border-radius:6px;font-family:\'Montserrat\',sans-serif;font-size:12px;font-weight:600;margin-right:8px;">Cronograma</a>'
            if email_url_disciplina:
                buttons_html += f'<a href="{email_url_disciplina}" style="display:inline-block;padding:10px 16px;background:#ffffff;color:#333333;text-decoration:none;border-radius:6px;font-family:\'Montserrat\',sans-serif;font-size:12px;font-weight:600;border:1px solid #e0e0e0;">Relatório Disciplinas</a>'
            buttons_html += '</td></tr></table></div>'
        
        return (html, buttons_html)
    
    def _generate_cronograma_team_section(self, schedule: Dict[str, Dict[str, List]],
                                          email_url_gant: Optional[str] = None,
                                          email_url_disciplina: Optional[str] = None) -> tuple:
        """Gera HTML da seção de cronograma para equipe - Design profissional Otus.
        
        Returns:
            Tupla (html_content, buttons_html) onde buttons_html pode ser vazio
        """
        if not schedule:
            html = '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#666;">Nenhuma atividade prevista para as próximas semanas.</p>'
        else:
            html = ""
            for discipline, categories in schedule.items():
                html += f'<div style="margin-bottom:24px;"><p style="margin:0 0 14px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:#1a1a1a;text-transform:uppercase;letter-spacing:1.5px;border-bottom:1px solid #eee;padding-bottom:6px;">{discipline}</p>'
                
                # A Iniciar
                if categories.get('a_iniciar'):
                    html += '<p style="margin:0 0 8px;font-family:\'Montserrat\',sans-serif;font-size:9px;font-weight:600;color:#f5a623;text-transform:uppercase;letter-spacing:1px;">● A Iniciar</p>'
                    for task in categories['a_iniciar']:
                        date = self._format_date(task.get('Data Término', task.get('Data de Término', '')))
                        name = task.get('Nome da Tarefa', task.get('Task Name', ''))
                        # Observação Otus
                        observacao_otus = task.get('Observação Otus', task.get('Observacao Otus', ''))
                        
                        html += f'<div style="margin-bottom:6px;padding-left:16px;">'
                        html += f'<p style="margin:0 0 4px;font-family:\'Source Sans Pro\',sans-serif;font-size:13px;color:#444;line-height:1.6;"><span style="font-family:\'Montserrat\',sans-serif;font-size:11px;color:#1a1a1a;font-weight:600;background:#f5f5f5;padding:2px 6px;border-radius:3px;margin-right:8px;">{date}</span>{name}</p>'
                        
                        if observacao_otus and str(observacao_otus).strip() and str(observacao_otus).lower() not in ['nan', 'none', '']:
                            html += f'<p style="margin:4px 0 0;font-family:\'Source Sans Pro\',sans-serif;font-size:12px;color:#f5a623;font-style:italic;padding-left:20px;"><span style="font-weight:600;color:#f5a623;">Observação Otus:</span> {observacao_otus}</p>'
                        
                        html += '</div>'
                
                # Entregas Programadas
                if categories.get('programadas'):
                    html += '<p style="margin:14px 0 8px;font-family:\'Montserrat\',sans-serif;font-size:9px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:1px;">● Entregas Programadas</p>'
                    for task in categories['programadas']:
                        date = self._format_date(task.get('Data Término', task.get('Data de Término', '')))
                        name = task.get('Nome da Tarefa', task.get('Task Name', ''))
                        # Observação Otus
                        observacao_otus = task.get('Observação Otus', task.get('Observacao Otus', ''))
                        
                        html += f'<div style="margin-bottom:6px;padding-left:16px;">'
                        html += f'<p style="margin:0 0 4px;font-family:\'Source Sans Pro\',sans-serif;font-size:13px;color:#666;line-height:1.6;"><span style="font-family:\'Montserrat\',sans-serif;font-size:11px;color:#666;font-weight:500;background:#f5f5f5;padding:2px 6px;border-radius:3px;margin-right:8px;">{date}</span>{name}</p>'
                        
                        if observacao_otus and str(observacao_otus).strip() and str(observacao_otus).lower() not in ['nan', 'none', '']:
                            html += f'<p style="margin:4px 0 0;font-family:\'Source Sans Pro\',sans-serif;font-size:12px;color:#f5a623;font-style:italic;padding-left:20px;"><span style="font-weight:600;color:#f5a623;">Observação Otus:</span> {observacao_otus}</p>'
                        
                        html += '</div>'
                
                html += '</div>'
        
        # Gerar botões separadamente - alinhados com os botões do rodapé
        buttons_html = ""
        if email_url_gant or email_url_disciplina:
            buttons_html = '<div style="margin-top:20px;padding:0;">'
            buttons_html += '<table cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td>'
            if email_url_gant:
                buttons_html += f'<a href="{email_url_gant}" style="display:inline-block;padding:10px 16px;background:#1a1a1a;color:#ffffff;text-decoration:none;border-radius:6px;font-family:\'Montserrat\',sans-serif;font-size:12px;font-weight:600;margin-right:8px;">Cronograma</a>'
            if email_url_disciplina:
                buttons_html += f'<a href="{email_url_disciplina}" style="display:inline-block;padding:10px 16px;background:#ffffff;color:#333333;text-decoration:none;border-radius:6px;font-family:\'Montserrat\',sans-serif;font-size:12px;font-weight:600;border:1px solid #e0e0e0;">Relatório Disciplinas</a>'
            buttons_html += '</td></tr></table></div>'
        
        return (html, buttons_html)
    
    def save_reports(self, data: Dict[str, Any], project_name: str, 
                    project_id: str = None, project_image_base64: Optional[str] = None,
                    email_url_gant: Optional[str] = None,
                    email_url_disciplina: Optional[str] = None) -> Dict[str, str]:
        """
        Salva os dois relatórios HTML (cliente e equipe).
        
        Args:
            data: Dados processados do projeto
            project_name: Nome do projeto
            project_id: ID do projeto
            project_image_base64: Imagem do projeto em base64 (opcional)
            email_url_gant: URL do cronograma Gantt (opcional)
            email_url_disciplina: URL do relatório de disciplinas (opcional)
            
        Returns:
            Dicionário com caminhos dos arquivos salvos
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        safe_name = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in project_name)
        safe_name = safe_name.replace(" ", "_").upper()
        
        paths = {}
        
        # Gerar e salvar relatório do cliente
        client_html = self.generate_client_report(data, project_id, project_image_base64, email_url_gant, email_url_disciplina)
        client_filename = f"Email_cliente_{safe_name}_{today_str}.html"
        client_path = os.path.join(self.reports_dir, client_filename)
        
        try:
            with open(client_path, 'w', encoding='utf-8') as f:
                f.write(client_html)
            paths['client'] = client_path
            logger.info(f"Relatório do cliente salvo em: {client_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar relatório do cliente: {e}")
        
        # Gerar e salvar relatório da equipe
        team_html = self.generate_team_report(data, project_id, project_image_base64, email_url_gant, email_url_disciplina)
        team_filename = f"Email_time_{safe_name}_{today_str}.html"
        team_path = os.path.join(self.reports_dir, team_filename)
        
        try:
            with open(team_path, 'w', encoding='utf-8') as f:
                f.write(team_html)
            paths['team'] = team_path
            logger.info(f"Relatório da equipe salvo em: {team_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar relatório da equipe: {e}")
        
        return paths
    
    def _get_project_image_html(self, project_image_base64: Optional[str] = None, 
                                project_name: str = "") -> str:
        """
        Gera HTML para a imagem do projeto.
        
        Args:
            project_image_base64: Imagem em base64 ou None
            project_name: Nome do projeto para alt text
            
        Returns:
            HTML da imagem ou placeholder
        """
        if project_image_base64:
            return f'''<img src="{project_image_base64}" alt="{project_name}" style="width:140px;height:140px;object-fit:cover;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.2);" />'''
        else:
            return '<div style="width:140px;height:140px;background:rgba(255,255,255,0.05);border-radius:12px;border:2px dashed rgba(255,255,255,0.15);display:inline-block;"></div>'

