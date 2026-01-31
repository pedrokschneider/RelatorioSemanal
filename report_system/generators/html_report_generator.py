"""
Gerador de relatórios em formato HTML para e-mail.
Gera dois tipos de relatório: um para clientes e outro para projetistas/time.
"""

import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import base64
import io
from functools import lru_cache

from ..config import ConfigManager

logger = logging.getLogger("ReportSystem")

# Tentar importar Pillow para processamento de imagens
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@lru_cache(maxsize=1)
def _get_logo_base64() -> str:
    """
    Carrega e processa a logo do arquivo Logo.png, retornando em base64.
    Usa lru_cache para thread-safety e evitar reprocessamento.

    Returns:
        String base64 da logo otimizada
    """
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

        return data_uri
        
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
    
    def _is_client_discipline(self, discipline: str) -> bool:
        """
        Verifica se a disciplina é do cliente ou Otus.
        Usa correspondência parcial para capturar variações como "Cliente da Coordenação" e "Coordenação".
        
        Args:
            discipline: Nome da disciplina
            
        Returns:
            True se a disciplina contém "cliente", "otus" ou "coordenação" (case-insensitive)
        """
        if not discipline:
            return False
        discipline_lower = str(discipline).strip().lower()
        # Normalizar "coordenação" removendo acentos para comparação
        discipline_normalized = discipline_lower.replace('ç', 'c').replace('ã', 'a')
        return ('cliente' in discipline_lower or 
                'otus' in discipline_lower or 
                'coordenacao' in discipline_normalized or
                'coordenação' in discipline_lower)

    def _normalize_status(self, value) -> str:
        if value is None:
            return ""
        import unicodedata
        import re
        text = str(value).strip().lower()
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        text = re.sub(r'\s+', ' ', text)
        return text

    def _has_delay_info(self, task: Dict) -> bool:
        delay_keys = [
            'Categoria de atraso',
            'Delay Category',
            'Motivo de atraso',
            'Motivo do atraso',
            'Delay Reason'
        ]
        for key in delay_keys:
            val = task.get(key)
            if val is not None and str(val).strip() not in ['', 'nan', 'None']:
                return True
        return False
    
    def generate_client_report(self, data: Dict[str, Any], project_id: str = None,
                               project_image_base64: Optional[str] = None,
                               email_url_gant: Optional[str] = None,
                               email_url_disciplina: Optional[str] = None,
                               show_dashboard_button: bool = True,
                               schedule_days: Optional[int] = None) -> str:
        """
        Gera relatório HTML para o cliente.
        
        Args:
            data: Dados processados do projeto
            project_id: ID do projeto (opcional)
            project_image_base64: Imagem do projeto em base64 (opcional)
            email_url_gant: URL do cronograma Gantt (opcional)
            email_url_disciplina: URL do relatório de disciplinas (opcional)
            show_dashboard_button: Se True, exibe o botão do Dashboard de Indicadores
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
            
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
        schedule = self._get_schedule_client(data, schedule_days=schedule_days)
        completed = self._get_completed_tasks_client(data)
        
        # Gerar seções HTML
        pendencias_html = self._generate_pendencias_section(client_issues, project_id)
        atrasos_html = self._generate_atrasos_client_section(delays)
        cronograma_html, _ = self._generate_cronograma_client_section(schedule, email_url_gant, email_url_disciplina, schedule_days=schedule_days)
        concluidas_html = self._generate_concluidas_section(completed, is_client_report=True)
        
        # Contagens para os badges
        count_pendencias = len(client_issues) if client_issues else 0
        count_atrasos = len(delays) if delays else 0
        count_cronograma = len(schedule) if schedule else 0
        count_concluidas = sum(len(tasks) for tasks in completed.values()) if completed else 0
        
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
                    'title': 'Atividades Concluídas',
                    'count': count_concluidas,
                    'color': '#16a34a',
                    'content': concluidas_html,
                    'open': False
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
            show_dashboard_button=show_dashboard_button,
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
                             email_url_disciplina: Optional[str] = None,
                             schedule_days: Optional[int] = None) -> str:
        """
        Gera relatório HTML para a equipe/projetistas.
        
        Args:
            data: Dados processados do projeto
            project_id: ID do projeto (opcional)
            project_image_base64: Imagem do projeto em base64 (opcional)
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
            
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
        schedule = self._get_schedule_team(data, schedule_days=schedule_days)
        
        # Gerar seções HTML
        concluidas_html = self._generate_concluidas_section(completed, is_client_report=False)
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
        except Exception as e:
            logger.debug(f"Falha ao obter nome do cliente via introspection: {e}")
        
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
        
        # CORREÇÃO: Não usar active_issues como fallback, pois pode incluir issues que não são do cliente
        # Se client_issues estiver vazio, significa que não há issues do cliente ou o filtro não funcionou
        # Nesse caso, retornar lista vazia para evitar mostrar issues incorretas
        if not client_issues:
            logger.warning("⚠️ Nenhuma issue do cliente encontrada. Verifique se as disciplinas do cliente estão configuradas corretamente na planilha.")
            return []
        
        # Filtrar apenas issues com status da disciplina = 'todo' (pendentes)
        # status_y = status da disciplina no Construflow
        todo_issues = []
        deadline_count = 0
        for issue in client_issues:
            status_disciplina = issue.get('status_y', '')
            if status_disciplina == 'todo':
                # Garantir que deadline seja preservado (pode vir como NaN do pandas)
                if 'deadline' in issue:
                    deadline_value = issue.get('deadline')
                    # Converter NaN/None para string vazia
                    if deadline_value is None or (isinstance(deadline_value, float) and pd.isna(deadline_value)):
                        issue['deadline'] = ''
                    else:
                        deadline_count += 1
                todo_issues.append(issue)
        
        logger.info(f"Issues do cliente com status 'todo': {len(todo_issues)} de {len(client_issues)}")
        if deadline_count > 0:
            logger.info(f"✅ {deadline_count} issues com deadline encontradas")
        return todo_issues
    
    def _get_completed_tasks(self, data: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Obtém tarefas concluídas agrupadas por disciplina.
        Para o relatório da equipe - mostra todas as disciplinas, EXCETO 'Cliente' e 'Otus' (que aparecem no relatório do cliente).
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            return {}
        
        all_tasks = smartsheet_data.get('all_tasks', [])
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Usar since_date se fornecido, senão usar última semana (7 dias)
        since_date = data.get('since_date')
        if since_date:
            # Garantir que since_date seja datetime se for string
            if isinstance(since_date, str):
                try:
                    since_date = datetime.fromisoformat(since_date)
                except ValueError:
                    try:
                        since_date = datetime.strptime(since_date, "%d/%m/%Y")
                    except ValueError:
                        logger.warning(f"Formato de since_date inválido: {since_date}, usando padrão de 7 dias")
                        since_date = None
            if since_date:
                since_date = since_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if not since_date:
            since_date = today - timedelta(days=7)
        
        completed_by_discipline = {}
        tasks_cliente_otus = 0
        for task in all_tasks:
            if not isinstance(task, dict):
                continue
            
            status = str(task.get('Status', '')).lower().strip()
            if status != 'feito':
                continue
            
            # Verificar se foi concluída desde a data inicial (se tiver data)
            end_date_str = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
            if end_date_str:
                try:
                    end_date = self._parse_date(end_date_str)
                    if end_date:
                        end_date_normalized = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        if end_date_normalized < since_date:
                            continue  # Ignorar tarefas concluídas antes da data inicial
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data de término '{end_date_str}': {e}")
            
            discipline = task.get('Disciplina', task.get('Discipline', 'Sem Disciplina')) or 'Sem Disciplina'
            # Excluir 'Cliente' e 'Otus' do relatório da equipe (serão mostrados no relatório do cliente)
            if self._is_client_discipline(discipline):
                tasks_cliente_otus += 1
                continue
            
            if discipline not in completed_by_discipline:
                completed_by_discipline[discipline] = []
            completed_by_discipline[discipline].append(task)
        
        total_completed = sum(len(tasks) for tasks in completed_by_discipline.values())
        logger.info(f"Tarefas concluídas da equipe: {total_completed} em {len(completed_by_discipline)} disciplinas")
        if tasks_cliente_otus > 0:
            logger.info(f"  - {tasks_cliente_otus} tarefas concluídas de 'Cliente' e 'Otus' excluídas (aparecem no relatório do cliente)")
        return completed_by_discipline
    
    def _get_completed_tasks_client(self, data: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        Obtém tarefas concluídas agrupadas por disciplina para o relatório do cliente.
        Filtra apenas tarefas das disciplinas 'Cliente' e 'Otus'.
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            logger.warning("⚠️ Dados do SmartSheet não encontrados para tarefas concluídas do cliente")
            return {}
        
        all_tasks = smartsheet_data.get('all_tasks', [])
        if not all_tasks:
            logger.warning("⚠️ Nenhuma tarefa encontrada no SmartSheet para tarefas concluídas")
            return {}
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Usar since_date se fornecido, senão usar última semana (7 dias)
        since_date = data.get('since_date')
        if since_date:
            # Garantir que since_date seja datetime se for string
            if isinstance(since_date, str):
                try:
                    since_date = datetime.fromisoformat(since_date)
                except ValueError:
                    try:
                        since_date = datetime.strptime(since_date, "%d/%m/%Y")
                    except ValueError:
                        logger.warning(f"Formato de since_date inválido: {since_date}, usando padrão de 7 dias")
                        since_date = None
            if since_date:
                since_date = since_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if not since_date:
            since_date = today - timedelta(days=7)
        
        completed_by_discipline = {}
        tasks_nao_concluidas = 0
        tasks_fora_periodo = 0
        tasks_outra_disciplina = 0
        tasks_sem_data = 0
        tasks_hoje = 0
        
        logger.info(f"Filtrando tarefas concluídas: período de {since_date.strftime('%d/%m/%Y')} até {today.strftime('%d/%m/%Y')} (inclusive)")
        
        for task in all_tasks:
            if not isinstance(task, dict):
                continue
            
            status = str(task.get('Status', '')).lower().strip()
            if status != 'feito':
                tasks_nao_concluidas += 1
                continue
            
            # Verificar se foi concluída na última semana (se tiver data)
            end_date_str = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
            task_name = task.get('Nome da Tarefa', task.get('Task Name', 'Sem nome'))
            
            if end_date_str:
                try:
                    end_date = self._parse_date(end_date_str)
                    if end_date:
                        # Normalizar para comparar apenas a data (sem hora)
                        end_date_normalized = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        # Incluir tarefas concluídas desde since_date até hoje (inclusive)
                        if end_date_normalized < since_date:
                            tasks_fora_periodo += 1
                            continue  # Ignorar tarefas concluídas antes da data inicial
                        elif end_date_normalized == today:
                            tasks_hoje += 1
                except Exception as e:
                    logger.debug(f"Erro ao parsear data '{end_date_str}' da tarefa '{task_name}': {e}")
            else:
                tasks_sem_data += 1
                # Tarefas sem data são incluídas se estiverem com status "feito"
            
            discipline = task.get('Disciplina', task.get('Discipline', 'Sem Disciplina')) or 'Sem Disciplina'
            # Filtrar apenas disciplinas do cliente (correspondência parcial)
            if not self._is_client_discipline(discipline):
                tasks_outra_disciplina += 1
                continue
            
            if discipline not in completed_by_discipline:
                completed_by_discipline[discipline] = []
            completed_by_discipline[discipline].append(task)
        
        total_completed = sum(len(tasks) for tasks in completed_by_discipline.values())
        logger.info(f"Tarefas concluídas do cliente: {total_completed} em {len(completed_by_discipline)} disciplinas de {len(all_tasks)} total")
        if tasks_nao_concluidas > 0:
            logger.info(f"  - {tasks_nao_concluidas} tarefas não concluídas")
        if tasks_fora_periodo > 0:
            logger.info(f"  - {tasks_fora_periodo} tarefas concluídas há mais de uma semana")
        if tasks_sem_data > 0:
            logger.info(f"  - {tasks_sem_data} tarefas sem data (incluídas)")
        if tasks_hoje > 0:
            logger.info(f"  - {tasks_hoje} tarefas concluídas hoje")
        if tasks_outra_disciplina > 0:
            logger.info(f"  - {tasks_outra_disciplina} tarefas de outras disciplinas (não 'Cliente' ou 'Otus')")
        
        return completed_by_discipline
    
    def _get_delays_client(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Obtém atrasos para relatório do cliente.
        Filtra tarefas atrasadas do SmartSheet onde Disciplina = 'Cliente' ou 'Otus'.
        Mostra apenas atrasos das últimas 2 semanas (relatório semanal).
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            logger.warning("⚠️ Dados do SmartSheet não encontrados para atrasos do cliente")
            return []
        
        delayed_tasks = smartsheet_data.get('delayed_tasks', [])
        if not delayed_tasks:
            logger.info("Nenhuma tarefa atrasada encontrada no SmartSheet")
            return []
        
        # Filtrar atrasos das últimas 2 semanas (relatório semanal)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        two_weeks_ago = today - timedelta(days=14)
        
        # Log: mostrar disciplinas únicas nas tarefas atrasadas
        disciplinas_atrasadas = set()
        for task in delayed_tasks:
            if isinstance(task, dict):
                disciplina = str(task.get('Disciplina', task.get('Discipline', ''))).strip()
                if disciplina:
                    disciplinas_atrasadas.add(disciplina)
        logger.info(f"Disciplinas nas tarefas atrasadas: {sorted(disciplinas_atrasadas)}")
        
        # Filtrar por disciplina "Cliente" ou "Otus" e por período (últimas 2 semanas)
        client_delays = []
        tasks_outra_disciplina = 0
        tasks_fora_periodo = 0
        
        for task in delayed_tasks:
            disciplina = task.get('Disciplina', task.get('Discipline', ''))
            
            # Filtrar por disciplina
            if not self._is_client_discipline(disciplina):
                tasks_outra_disciplina += 1
                continue
            
            # Incluir atrasos explícitos mesmo fora do período
            status_norm = self._normalize_status(task.get('Status', ''))
            atraso_explicito = status_norm == 'nao feito' or self._has_delay_info(task)
            if atraso_explicito:
                client_delays.append(task)
                continue

            # Verificar se o atraso está nas últimas 2 semanas
            # Usar data de término (ou baseline se disponível) para verificar se está atrasado nas últimas 2 semanas
            task_date = None
            end_date_str = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
            baseline_date_str = task.get('Data de Fim - Baseline Otus', '')
            
            # Priorizar baseline, senão usar data de término
            if baseline_date_str:
                try:
                    task_date = self._parse_date(baseline_date_str)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data baseline '{baseline_date_str}': {e}")

            if not task_date and end_date_str:
                try:
                    task_date = self._parse_date(end_date_str)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data término '{end_date_str}': {e}")

            # Se tem data, verificar se está nas últimas 2 semanas
            if task_date:
                task_date_normalized = task_date.replace(hour=0, minute=0, second=0, microsecond=0)
                # Incluir atrasos que deveriam ter sido concluídos nas últimas 2 semanas
                if task_date_normalized >= two_weeks_ago and task_date_normalized <= today:
                    client_delays.append(task)
                else:
                    tasks_fora_periodo += 1
            else:
                # Se não tem data, incluir (pode ser tarefa sem data definida mas marcada como atrasada)
                client_delays.append(task)

        logger.info(f"Atrasos do cliente: {len(client_delays)} de {len(delayed_tasks)} atrasadas (últimas 2 semanas)")
        if tasks_outra_disciplina > 0:
            logger.info(f"  - {tasks_outra_disciplina} tarefas atrasadas de outras disciplinas (não 'Cliente' ou 'Otus')")
        if tasks_fora_periodo > 0:
            logger.info(f"  - {tasks_fora_periodo} tarefas atrasadas fora do período (mais de 2 semanas)")
        
        return client_delays
    
    def _get_delays_team(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Obtém atrasos para relatório da equipe.
        Retorna todas as tarefas atrasadas, EXCETO 'Cliente' e 'Otus' (que aparecem no relatório do cliente).
        Mostra apenas atrasos das últimas 2 semanas (relatório semanal).
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            return []
        
        delayed_tasks = smartsheet_data.get('delayed_tasks', [])
        
        # Filtrar atrasos das últimas 2 semanas (relatório semanal)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        two_weeks_ago = today - timedelta(days=14)
        
        # Excluir 'Cliente' e 'Otus' do relatório da equipe e filtrar por período
        team_delays = []
        tasks_cliente_otus = 0
        tasks_fora_periodo = 0
        
        for task in delayed_tasks:
            disciplina = task.get('Disciplina', task.get('Discipline', ''))
            
            # Excluir disciplinas do cliente
            if self._is_client_discipline(disciplina):
                tasks_cliente_otus += 1
                continue
            
            # Incluir atrasos explícitos mesmo fora do período
            status_norm = self._normalize_status(task.get('Status', ''))
            atraso_explicito = status_norm == 'nao feito' or self._has_delay_info(task)
            if atraso_explicito:
                team_delays.append(task)
                continue

            # Verificar se o atraso está nas últimas 2 semanas
            task_date = None
            end_date_str = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
            baseline_date_str = task.get('Data de Fim - Baseline Otus', '')
            
            # Priorizar baseline, senão usar data de término
            if baseline_date_str:
                try:
                    task_date = self._parse_date(baseline_date_str)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data baseline '{baseline_date_str}': {e}")

            if not task_date and end_date_str:
                try:
                    task_date = self._parse_date(end_date_str)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data término '{end_date_str}': {e}")

            # Se tem data, verificar se está nas últimas 2 semanas
            if task_date:
                task_date_normalized = task_date.replace(hour=0, minute=0, second=0, microsecond=0)
                # Incluir atrasos que deveriam ter sido concluídos nas últimas 2 semanas
                if task_date_normalized >= two_weeks_ago and task_date_normalized <= today:
                    team_delays.append(task)
                else:
                    tasks_fora_periodo += 1
            else:
                # Se não tem data, incluir (pode ser tarefa sem data definida mas marcada como atrasada)
                team_delays.append(task)

        logger.info(f"Atrasos da equipe: {len(team_delays)} tarefas atrasadas (últimas 2 semanas)")
        if tasks_cliente_otus > 0:
            logger.info(f"  - {tasks_cliente_otus} tarefas atrasadas de 'Cliente' e 'Otus' excluídas (aparecem no relatório do cliente)")
        if tasks_fora_periodo > 0:
            logger.info(f"  - {tasks_fora_periodo} tarefas atrasadas fora do período (mais de 2 semanas)")
        return team_delays
    
    def _get_schedule_client(self, data: Dict[str, Any], schedule_days: Optional[int] = None) -> List[Dict]:
        """
        Obtém cronograma para o cliente (entregas importantes).
        Filtra tarefas do SmartSheet onde Disciplina = 'Cliente' ou 'Otus' e que estão programadas.
        
        Args:
            data: Dados processados do projeto
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            logger.warning("⚠️ Dados do SmartSheet não encontrados para cronograma do cliente")
            return []
        
        all_tasks = smartsheet_data.get('all_tasks', [])
        if not all_tasks:
            logger.warning("⚠️ Nenhuma tarefa encontrada no SmartSheet")
            return []
        
        # Usar schedule_days se fornecido, senão usar padrão de 15 dias
        days = schedule_days if schedule_days is not None and schedule_days > 0 else 15
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        future_cutoff = today + timedelta(days=days)
        
        # Log: mostrar disciplinas únicas encontradas no SmartSheet
        disciplinas_encontradas = set()
        disciplinas_com_cliente = []
        for task in all_tasks:
            if isinstance(task, dict):
                disciplina = str(task.get('Disciplina', task.get('Discipline', ''))).strip()
                if disciplina:
                    disciplinas_encontradas.add(disciplina)
                    # Verificar se esta disciplina seria considerada do cliente
                    if self._is_client_discipline(disciplina):
                        disciplinas_com_cliente.append(disciplina)
        logger.info(f"Disciplinas encontradas no SmartSheet: {sorted(disciplinas_encontradas)}")
        if disciplinas_com_cliente:
            logger.info(f"⚠️ Disciplinas identificadas como do cliente/Otus: {sorted(set(disciplinas_com_cliente))}")
        else:
            logger.warning(f"⚠️ NENHUMA disciplina foi identificada como do cliente/Otus! Verifique se há disciplinas com 'Cliente', 'Otus' ou 'Coordenação'")
        
        # Filtrar tarefas do cliente ou Otus que estão programadas (não concluídas)
        client_schedule = []
        tasks_sem_data = 0
        tasks_fora_periodo = 0
        tasks_concluidas = 0
        tasks_outra_disciplina = 0
        tasks_iniciando = 0
        tasks_terminando = 0
        
        for task in all_tasks:
            if not isinstance(task, dict):
                continue
            
            # Verificar disciplina (correspondência parcial para capturar "Cliente da Coordenação", etc.)
            disciplina = task.get('Disciplina', task.get('Discipline', ''))
            if not self._is_client_discipline(disciplina):
                tasks_outra_disciplina += 1
                continue
            
            # Verificar status (apenas tarefas não concluídas)
            status = str(task.get('Status', '')).lower().strip()
            if status == 'feito':
                tasks_concluidas += 1
                continue
            
            # Verificar datas: incluir tarefas que INICIAM ou TERMINAM no período
            task_start_str = task.get('Data Inicio', task.get('Data de Início', task.get('Start Date', '')))
            task_end_str = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
            
            if not task_start_str and not task_end_str:
                tasks_sem_data += 1
                continue
            
            # Verificar se a tarefa inicia ou termina no período
            task_in_period = False
            starts_in_period = False
            ends_in_period = False
            start_date = None
            end_date = None
            
            if task_start_str:
                try:
                    start_date = self._parse_date(task_start_str)
                    if start_date:
                        # Normalizar para comparar apenas a data (sem hora)
                        start_date_normalized = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        if start_date_normalized >= today and start_date_normalized <= future_cutoff:
                            task_in_period = True
                            starts_in_period = True
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data início '{task_start_str}': {e}")

            if task_end_str:
                try:
                    end_date = self._parse_date(task_end_str)
                    if end_date:
                        # Normalizar para comparar apenas a data (sem hora)
                        end_date_normalized = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        if end_date_normalized >= today and end_date_normalized <= future_cutoff:
                            task_in_period = True
                            ends_in_period = True
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data término '{task_end_str}': {e}")

            if task_in_period:
                client_schedule.append(task)
                if starts_in_period:
                    tasks_iniciando += 1
                if ends_in_period:
                    tasks_terminando += 1
            else:
                tasks_fora_periodo += 1

        # Ordenar por data
        client_schedule.sort(key=lambda x: self._parse_date(x.get('Data Término', x.get('Data de Término', x.get('End Date', '')))) or datetime.max)
        
        logger.info(f"Cronograma do cliente: {len(client_schedule)} tarefas programadas de {len(all_tasks)} total (período: {days} dias)")
        if tasks_iniciando > 0:
            logger.info(f"  - {tasks_iniciando} tarefas que INICIAM no período")
        if tasks_terminando > 0:
            logger.info(f"  - {tasks_terminando} tarefas que TERMINAM no período")
        if tasks_outra_disciplina > 0:
            logger.info(f"  - {tasks_outra_disciplina} tarefas de outras disciplinas (não 'Cliente' ou 'Otus')")
        if tasks_concluidas > 0:
            logger.info(f"  - {tasks_concluidas} tarefas já concluídas")
        if tasks_sem_data > 0:
            logger.info(f"  - {tasks_sem_data} tarefas sem data de início/término")
        if tasks_fora_periodo > 0:
            logger.info(f"  - {tasks_fora_periodo} tarefas fora do período (próximos {days} dias)")
        
        return client_schedule
    
    def _get_schedule_team(self, data: Dict[str, Any], schedule_days: Optional[int] = None) -> Dict[str, Dict[str, List]]:
        """
        Obtém cronograma detalhado para a equipe.
        Exclui disciplinas 'Cliente' e 'Otus' (que aparecem no relatório do cliente).
        
        Args:
            data: Dados processados do projeto
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if not smartsheet_data:
            return {}
        
        all_tasks = smartsheet_data.get('all_tasks', [])
        
        # Usar schedule_days se fornecido, senão usar padrão de 15 dias
        days = schedule_days if schedule_days is not None and schedule_days > 0 else 15
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        future_cutoff = today + timedelta(days=days)
        
        schedule = {}
        tasks_cliente_otus = 0
        tasks_iniciando = 0
        tasks_terminando = 0
        tasks_fora_periodo = 0
        
        for task in all_tasks:
            if not isinstance(task, dict):
                continue
            
            discipline = task.get('Disciplina', 'Sem Disciplina') or 'Sem Disciplina'
            # Excluir 'Cliente' e 'Otus' do relatório da equipe (serão mostrados no relatório do cliente)
            if self._is_client_discipline(discipline):
                tasks_cliente_otus += 1
                continue
            
            # Verificar datas: incluir tarefas que INICIAM ou TERMINAM no período
            task_start_str = task.get('Data Inicio', task.get('Data de Início', task.get('Start Date', '')))
            task_end_str = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
            
            if not task_start_str and not task_end_str:
                    continue
            
            # Verificar se a tarefa inicia ou termina no período
            task_in_period = False
            starts_in_period = False
            ends_in_period = False
            
            if task_start_str:
                try:
                    start_date = self._parse_date(task_start_str)
                    if start_date:
                        # Normalizar para comparar apenas a data (sem hora)
                        start_date_normalized = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        if start_date_normalized >= today and start_date_normalized <= future_cutoff:
                            task_in_period = True
                            starts_in_period = True
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data início '{task_start_str}': {e}")

            if task_end_str:
                try:
                    end_date = self._parse_date(task_end_str)
                    if end_date:
                        # Normalizar para comparar apenas a data (sem hora)
                        end_date_normalized = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                        if end_date_normalized >= today and end_date_normalized <= future_cutoff:
                            task_in_period = True
                            ends_in_period = True
                except (ValueError, TypeError) as e:
                    logger.debug(f"Falha ao processar data término '{task_end_str}': {e}")

            if not task_in_period:
                tasks_fora_periodo += 1
                continue
            
            status = str(task.get('Status', '')).lower().strip()
            
            if discipline not in schedule:
                schedule[discipline] = {'a_iniciar': [], 'programadas': []}
            
            if status == 'a fazer':
                schedule[discipline]['a_iniciar'].append(task)
            else:
                schedule[discipline]['programadas'].append(task)
            
            if starts_in_period:
                tasks_iniciando += 1
            if ends_in_period:
                tasks_terminando += 1
        
        total_tasks = sum(len(tasks) for disc in schedule.values() for tasks in disc.values())
        logger.info(f"Cronograma da equipe: {total_tasks} tarefas programadas em {len(schedule)} disciplinas (período: {days} dias)")
        if tasks_iniciando > 0:
            logger.info(f"  - {tasks_iniciando} tarefas que INICIAM no período")
        if tasks_terminando > 0:
            logger.info(f"  - {tasks_terminando} tarefas que TERMINAM no período")
        if tasks_cliente_otus > 0:
            logger.info(f"  - {tasks_cliente_otus} tarefas de 'Cliente' e 'Otus' excluídas (aparecem no relatório do cliente)")
        if tasks_fora_periodo > 0:
            logger.info(f"  - {tasks_fora_periodo} tarefas fora do período (próximos {days} dias)")
        
        return schedule
    
    def _parse_date(self, date_str) -> Optional[datetime]:
        """Parse flexível de datas."""
        if not date_str:
            return None
        
        # Verificar se é NaT (Not a Time) do pandas
        try:
            if pd.isna(date_str):
                return None
        except (TypeError, ValueError):
            pass
        
        if hasattr(date_str, 'strftime'):
            # Verificar se o objeto datetime não é NaT
            try:
                if pd.isna(date_str):
                    return None
            except (TypeError, ValueError):
                pass
            return date_str
        
        if not isinstance(date_str, str):
            return None
        
        formats = ["%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d/%m", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
    
    def _format_date(self, date_value) -> str:
        """Formata data para dd/mm."""
        if not date_value:
            return ""
        
        # Verificar se é NaT (Not a Time) do pandas
        try:
            if pd.isna(date_value):
                return ""
        except (TypeError, ValueError):
            pass
        
        dt = self._parse_date(date_value)
        if dt:
            # Verificar se dt não é NaT antes de formatar
            try:
                if pd.isna(dt):
                    return ""
            except (TypeError, ValueError):
                pass
            return dt.strftime("%d/%m")
        
        # Fallback - verificar se é NaT antes de converter para string
        try:
            if pd.isna(date_value):
                return ""
        except (TypeError, ValueError):
            pass
        
        return str(date_value)[:5]

    def _format_start_end_range(self, start_date, end_date) -> str:
        """Formata intervalo início/fim para 'dd/mm a dd/mm'."""
        def has_value(value) -> bool:
            if value is None:
                return False
            text = str(value).strip().lower()
            return text not in ['nan', 'none', 'nat', '']

        start_ok = has_value(start_date)
        end_ok = has_value(end_date)

        if start_ok and end_ok:
            start_fmt = self._format_date(start_date)
            end_fmt = self._format_date(end_date)
            if start_fmt and end_fmt and start_fmt != end_fmt:
                return f"{start_fmt} a {end_fmt}"
            return start_fmt or end_fmt
        if start_ok:
            return self._format_date(start_date)
        if end_ok:
            return self._format_date(end_date)
        return ""
    
    def _format_deadline_date(self, deadline_value) -> str:
        """Formata deadline (formato ISO) para dd/mm/yyyy."""
        if not deadline_value:
            return ""
        
        # Verificar se é NaN do pandas
        try:
            if pd.isna(deadline_value):
                return ""
        except (TypeError, ValueError):
            pass
        
        # Tentar parsear formato ISO (2021-02-24T03:00:00.000Z)
        try:
            if isinstance(deadline_value, str):
                deadline_str = str(deadline_value).strip()
                if not deadline_str or deadline_str.lower() in ['nan', 'none', 'nat', '']:
                    return ""
                # Remover 'Z' e milissegundos se existirem
                deadline_clean = deadline_str.replace('Z', '').split('.')[0]
                # Tentar parsear formato ISO
                dt = datetime.strptime(deadline_clean, "%Y-%m-%dT%H:%M:%S")
                return dt.strftime("%d/%m/%Y")
            elif hasattr(deadline_value, 'strftime'):
                # Já é um objeto datetime
                return deadline_value.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            # Se falhar, tentar usar o parser genérico
            dt = self._parse_date(deadline_value)
            if dt:
                return dt.strftime("%d/%m/%Y")
        
        # Fallback: retornar string original truncada
        return str(deadline_value)[:10] if deadline_value else ""
    
    def _generate_pendencias_section(self, issues: List[Dict], project_id: str) -> str:
        """Gera HTML da seção de pendências do cliente - Design profissional Otus.
        Agrupa por disciplina e, dentro de cada disciplina, por prioridade.
        """
        # Paleta profissional minimalista
        color_high = "#1a1a1a"      # Preto Otus para alta prioridade
        color_medium = "#666666"    # Cinza médio para média prioridade  
        color_low = "#999999"       # Cinza claro para baixa
        accent = "#f5a623"          # Laranja Otus apenas para destaques sutis
        
        if not issues:
            return '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#1a1a1a;">✓ Sem pendências das disciplinas <strong>Cliente</strong> e <strong>Otus</strong> nesta semana.</p>'
        
        # Agrupar primeiro por disciplina, depois por prioridade
        by_discipline = {}
        
        for issue in issues:
            # Obter disciplina (campo 'name' da issue)
            discipline = issue.get('name', 'Sem Disciplina') or 'Sem Disciplina'
            
            if discipline not in by_discipline:
                by_discipline[discipline] = {
                    'alta': [],
                    'media': [],
                    'baixa': []
                }
            
            priority = str(issue.get('priority', '')).lower()
            issue_data = {
                'code': issue.get('code', ''),
                'title': issue.get('title', 'Sem título'),
                'id': issue.get('id', ''),
                'deadline': issue.get('deadline', '')  # Data limite da disciplina
            }
            
            if priority in ['high', 'alta', '3']:
                by_discipline[discipline]['alta'].append(issue_data)
            elif priority in ['medium', 'media', 'média', '2']:
                by_discipline[discipline]['media'].append(issue_data)
            else:
                by_discipline[discipline]['baixa'].append(issue_data)
        
        html = ""
        
        # Iterar por disciplina
        for discipline, priorities in by_discipline.items():
            # Só criar seção da disciplina se houver issues
            if not priorities['alta'] and not priorities['media'] and not priorities['baixa']:
                continue
            
            html += f'<div style="margin-bottom:24px;"><p style="margin:0 0 12px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:#1a1a1a;text-transform:uppercase;letter-spacing:1.5px;border-bottom:1px solid #eee;padding-bottom:6px;">{discipline}</p>'
            
            # Prioridade Alta - destaque máximo
            if priorities['alta']:
                html += '<div style="margin-bottom:16px;padding-left:12px;">'
                html += f'<p style="margin:0 0 8px;font-family:\'Montserrat\',sans-serif;font-size:9px;font-weight:700;color:{color_high};text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid {color_high};padding-bottom:4px;display:inline-block;">Prioridade Alta</p>'
                html += '<div style="padding-left:0;">'
                for item in priorities['alta']:
                    url = f"https://app.construflow.com.br/workspace/project/{project_id}/issues?issueId={item['id']}"
                    issue_code = item.get('code', item.get('id', ''))
                    deadline_html = ""
                    deadline_value = item.get('deadline')
                    # Verificar se deadline existe e não é None/NaN/vazio
                    if deadline_value is not None:
                        deadline_str = str(deadline_value).strip()
                        if deadline_str and deadline_str.lower() not in ['nan', 'none', '', 'nat']:
                            deadline_date = self._format_deadline_date(deadline_value)
                            if deadline_date:
                                deadline_html = f'<span style="margin-left:8px;font-family:\'Montserrat\',sans-serif;font-size:11px;color:#f5a623;font-weight:600;background:#fff3e0;padding:2px 8px;border-radius:3px;">⏰ {deadline_date}</span>'
                    # Destacar o link com ID do apontamento ANTES do título
                    link_text = f'🔗 <span style="font-family:\'Montserrat\',sans-serif;font-size:11px;color:#f5a623;font-weight:600;background:#fff3e0;padding:2px 6px;border-radius:3px;margin-right:8px;">{issue_code}</span>{item["title"]}'
                    html += f'<p style="margin:0 0 8px;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#1a1a1a;line-height:1.7;padding:8px 12px;background:#f8f8f8;border-radius:4px;border-left:3px solid {accent};"><a href="{url}" style="color:#1a1a1a;text-decoration:underline;font-weight:500;border-bottom:1px solid #f5a623;">{link_text}</a>{deadline_html}</p>'
                html += '</div></div>'
            
            # Prioridade Média
            if priorities['media']:
                html += '<div style="margin-bottom:16px;padding-left:12px;">'
                html += f'<p style="margin:0 0 8px;font-family:\'Montserrat\',sans-serif;font-size:9px;font-weight:700;color:{color_medium};text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #ddd;padding-bottom:4px;display:inline-block;">Prioridade Média</p>'
                html += '<div style="padding-left:0;">'
                for item in priorities['media']:
                    url = f"https://app.construflow.com.br/workspace/project/{project_id}/issues?issueId={item['id']}"
                    issue_code = item.get('code', item.get('id', ''))
                    deadline_html = ""
                    deadline_value = item.get('deadline')
                    # Verificar se deadline existe e não é None/NaN/vazio
                    if deadline_value is not None:
                        deadline_str = str(deadline_value).strip()
                        if deadline_str and deadline_str.lower() not in ['nan', 'none', '', 'nat']:
                            deadline_date = self._format_deadline_date(deadline_value)
                            if deadline_date:
                                deadline_html = f'<span style="margin-left:8px;font-family:\'Montserrat\',sans-serif;font-size:11px;color:#f5a623;font-weight:600;background:#fff3e0;padding:2px 8px;border-radius:3px;">⏰ {deadline_date}</span>'
                    # Destacar o link com ID do apontamento ANTES do título
                    link_text = f'🔗 <span style="font-family:\'Montserrat\',sans-serif;font-size:10px;color:#f5a623;font-weight:600;background:#fff3e0;padding:2px 6px;border-radius:3px;margin-right:8px;">{issue_code}</span>{item["title"]}'
                    html += f'<p style="margin:0 0 6px;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#444;line-height:1.7;padding:6px 12px;border-left:2px solid #ddd;"><a href="{url}" style="color:#444;text-decoration:underline;border-bottom:1px solid #f5a623;">{link_text}</a>{deadline_html}</p>'
                html += '</div></div>'
            
            # Prioridade Baixa
            if priorities['baixa']:
                html += '<div style="margin-bottom:16px;padding-left:12px;">'
                html += f'<p style="margin:0 0 8px;font-family:\'Montserrat\',sans-serif;font-size:9px;font-weight:700;color:{color_low};text-transform:uppercase;letter-spacing:1px;">Prioridade Baixa</p>'
                html += '<div style="padding-left:0;">'
                for item in priorities['baixa']:
                    url = f"https://app.construflow.com.br/workspace/project/{project_id}/issues?issueId={item['id']}"
                    issue_code = item.get('code', item.get('id', ''))
                    deadline_html = ""
                    deadline_value = item.get('deadline')
                    # Verificar se deadline existe e não é None/NaN/vazio
                    if deadline_value is not None:
                        deadline_str = str(deadline_value).strip()
                        if deadline_str and deadline_str.lower() not in ['nan', 'none', '', 'nat']:
                            deadline_date = self._format_deadline_date(deadline_value)
                            if deadline_date:
                                deadline_html = f'<span style="margin-left:8px;font-family:\'Montserrat\',sans-serif;font-size:10px;color:#f5a623;font-weight:600;background:#fff3e0;padding:2px 6px;border-radius:3px;">⏰ {deadline_date}</span>'
                    # Destacar o link com ID do apontamento ANTES do título
                    link_text = f'🔗 <span style="font-family:\'Montserrat\',sans-serif;font-size:10px;color:#f5a623;font-weight:600;background:#fff3e0;padding:2px 6px;border-radius:3px;margin-right:8px;">{issue_code}</span>{item["title"]}'
                    html += f'<p style="margin:0 0 6px;font-family:\'Source Sans Pro\',sans-serif;font-size:13px;color:#666;line-height:1.6;padding-left:12px;"><a href="{url}" style="color:#666;text-decoration:underline;border-bottom:1px solid #f5a623;">{link_text}</a>{deadline_html}</p>'
                html += '</div></div>'
            
            html += '</div>'
        
        return html
    
    def _generate_concluidas_section(self, completed: Dict[str, List[Dict]], is_client_report: bool = True) -> str:
        """Gera HTML da seção de atividades concluídas - Design profissional Otus.
        
        Args:
            completed: Dicionário com tarefas concluídas agrupadas por disciplina
            is_client_report: Se True, é relatório do cliente (menciona Cliente e Otus). Se False, é relatório da equipe.
        """
        if not completed:
            if is_client_report:
                return '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#666;">✓ Nenhuma atividade concluída das disciplinas <strong>Cliente</strong> e <strong>Otus</strong> no período (últimos 7 dias).</p>'
            else:
                return '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#666;">✓ Nenhuma atividade concluída no período (últimos 7 dias).</p>'
        
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
            return '<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#1a1a1a;">✓ Nenhum atraso identificado das disciplinas <strong>Cliente</strong> e <strong>Otus</strong> no período.</p>'
        
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
                                            email_url_disciplina: Optional[str] = None,
                                            schedule_days: Optional[int] = None) -> tuple:
        """Gera HTML da seção de cronograma para cliente - Design profissional Otus.
        
        Args:
            schedule: Lista de tarefas do cronograma
            email_url_gant: URL do cronograma Gantt (opcional)
            email_url_disciplina: URL do relatório de disciplinas (opcional)
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
        
        Returns:
            Tupla (html_content, buttons_html) onde buttons_html pode ser vazio
        """
        days = schedule_days if schedule_days is not None and schedule_days > 0 else 15
        if not schedule:
            html = f'<p style="margin:0;font-family:\'Source Sans Pro\',sans-serif;font-size:14px;color:#666;">✓ Nenhuma atividade prevista das disciplinas <strong>Cliente</strong> e <strong>Otus</strong> para os próximos {days} dias.</p>'
        else:
            # Agrupar por disciplina e separar por status (a iniciar vs programadas)
            by_discipline = {}
            for task in schedule:
                if not isinstance(task, dict):
                    continue
                discipline = task.get('Disciplina', 'Sem Disciplina')
                if discipline not in by_discipline:
                    by_discipline[discipline] = {'a_iniciar': [], 'programadas': []}
                
                # Verificar status para separar "a iniciar" de "programadas"
                status = str(task.get('Status', '')).lower().strip()
                if status == 'a fazer':
                    by_discipline[discipline]['a_iniciar'].append(task)
                else:
                    by_discipline[discipline]['programadas'].append(task)
            
            html = ""
            for discipline, categories in by_discipline.items():
                # Só criar seção da disciplina se houver tarefas
                if not categories['a_iniciar'] and not categories['programadas']:
                    continue
                
                html += f'<div style="margin-bottom:24px;"><p style="margin:0 0 14px;font-family:\'Montserrat\',sans-serif;font-size:10px;font-weight:700;color:#1a1a1a;text-transform:uppercase;letter-spacing:1.5px;border-bottom:1px solid #eee;padding-bottom:6px;">{discipline}</p>'
                
                # A Iniciar
                if categories['a_iniciar']:
                    html += '<p style="margin:0 0 8px;font-family:\'Montserrat\',sans-serif;font-size:9px;font-weight:600;color:#f5a623;text-transform:uppercase;letter-spacing:1px;">● A Iniciar</p>'
                    for task in categories['a_iniciar']:
                        # Mostrar data de início se disponível, senão data de término
                        start_date = task.get('Data Inicio', task.get('Data de Início', task.get('Start Date', '')))
                        end_date = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
                        date = self._format_start_end_range(start_date, end_date)
                        name = task.get('Nome da Tarefa', task.get('Task Name', ''))
                        # Observação Otus
                        observacao_otus = task.get('Observação Otus', task.get('Observacao Otus', ''))
                        
                        html += f'<div style="margin-bottom:6px;padding-left:16px;">'
                        html += f'<p style="margin:0 0 4px;font-family:\'Source Sans Pro\',sans-serif;font-size:13px;color:#444;line-height:1.6;"><span style="font-family:\'Montserrat\',sans-serif;font-size:11px;color:#1a1a1a;font-weight:600;background:#f5f5f5;padding:2px 6px;border-radius:3px;margin-right:8px;">{date}</span>{name}</p>'
                        
                        if observacao_otus and str(observacao_otus).strip() and str(observacao_otus).lower() not in ['nan', 'none', '']:
                            html += f'<p style="margin:4px 0 0;font-family:\'Source Sans Pro\',sans-serif;font-size:12px;color:#f5a623;font-style:italic;padding-left:20px;"><span style="font-weight:600;color:#f5a623;">Observação Otus:</span> {observacao_otus}</p>'
                        
                        html += '</div>'
                
                # Entregas Programadas
                if categories['programadas']:
                    html += '<p style="margin:14px 0 8px;font-family:\'Montserrat\',sans-serif;font-size:9px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:1px;">● Entregas Programadas</p>'
                    for task in categories['programadas']:
                        date = self._format_date(task.get('Data Término', task.get('Data de Término', task.get('End Date', ''))))
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
                        # Mostrar data de início se disponível, senão data de término
                        start_date = task.get('Data Inicio', task.get('Data de Início', task.get('Start Date', '')))
                        end_date = task.get('Data Término', task.get('Data de Término', task.get('End Date', '')))
                        date = self._format_start_end_range(start_date, end_date)
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
                    email_url_disciplina: Optional[str] = None,
                    show_dashboard_button: bool = True,
                    schedule_days: Optional[int] = None) -> Dict[str, str]:
        """
        Salva os dois relatórios HTML (cliente e equipe).
        
        Args:
            data: Dados processados do projeto
            project_name: Nome do projeto
            project_id: ID do projeto
            project_image_base64: Imagem do projeto em base64 (opcional)
            email_url_gant: URL do cronograma Gantt (opcional)
            email_url_disciplina: URL do relatório de disciplinas (opcional)
            show_dashboard_button: Se True, exibe o botão do Dashboard de Indicadores no relatório do cliente
            schedule_days: Número de dias para o cronograma (None = padrão de 15 dias)
            
        Returns:
            Dicionário com caminhos dos arquivos salvos
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        safe_name = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in project_name)
        safe_name = safe_name.replace(" ", "_").upper()
        
        paths = {}
        
        # Gerar e salvar relatório do cliente
        client_html = self.generate_client_report(data, project_id, project_image_base64, email_url_gant, email_url_disciplina, show_dashboard_button, schedule_days=schedule_days)
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
        team_html = self.generate_team_report(data, project_id, project_image_base64, email_url_gant, email_url_disciplina, schedule_days=schedule_days)
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

