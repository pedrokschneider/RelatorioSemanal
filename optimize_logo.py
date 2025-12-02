"""
Script para otimizar a logo da Otus e gerar base64 otimizado.
"""

from PIL import Image
import io
import base64
import os

def optimize_logo(input_path='Logo.png', max_size=(200, 200), quality=85):
    """
    Otimiza a logo e retorna como base64.
    
    Args:
        input_path: Caminho da imagem original
        max_size: Tamanho máximo (largura, altura)
        quality: Qualidade JPEG (1-100)
    
    Returns:
        String base64 otimizada
    """
    if not os.path.exists(input_path):
        print(f"Arquivo {input_path} não encontrado!")
        return None
    
    try:
        # Abrir a imagem
        img = Image.open(input_path)
        
        # Converter para RGB se necessário
        if img.mode in ('RGBA', 'LA', 'P'):
            # Criar fundo branco para imagens com transparência
            rgb_image = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            rgb_image.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_image
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Redimensionar mantendo proporção
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Salvar em buffer como JPEG otimizado
        output_buffer = io.BytesIO()
        img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
        output_buffer.seek(0)
        
        # Converter para base64
        base64_content = base64.b64encode(output_buffer.read()).decode('utf-8')
        
        # Retornar no formato data URI
        data_uri = f"data:image/jpeg;base64,{base64_content}"
        
        # Mostrar estatísticas
        original_size = os.path.getsize(input_path)
        optimized_size = len(base64_content) * 3 / 4  # Aproximação do tamanho binário
        reduction = (1 - optimized_size / original_size) * 100
        
        print(f"✅ Logo otimizada com sucesso!")
        print(f"   Tamanho original: {original_size:,} bytes")
        print(f"   Tamanho otimizado: {int(optimized_size):,} bytes")
        print(f"   Redução: {reduction:.1f}%")
        print(f"   Dimensões: {img.size[0]}x{img.size[1]}px")
        print(f"\n📋 Base64 (primeiros 100 caracteres):")
        print(f"   {data_uri[:100]}...")
        
        return data_uri
        
    except Exception as e:
        print(f"❌ Erro ao otimizar logo: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    logo_base64 = optimize_logo()
    
    if logo_base64:
        # Salvar em arquivo para fácil cópia
        with open('logo_optimized_base64.txt', 'w', encoding='utf-8') as f:
            f.write(logo_base64)
        print(f"\n💾 Base64 completo salvo em: logo_optimized_base64.txt")




