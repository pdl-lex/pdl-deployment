# tei_to_json.py
import json
from lxml import etree
from pathlib import Path
from typing import Dict, List, Any
import sys
import xmltodict
from datetime import datetime

# ============================================================================
# KONFIGURATION - Hier Standardwerte anpassen
# ============================================================================
DEFAULT_INPUT_DIR = r'C:\Users\di97kok\Daten\Nextcloud\BAdW\BDO XML Daten\XML to TL0\outputdata'      # Eingabeverzeichnis für TEI-XML-Dateien
DEFAULT_OUTPUT_DIR = './output_json'   # Ausgabeverzeichnis für JSON-Dateien
# ============================================================================

# TEI Namespace
TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}

class TEIConverter:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        # Erstelle Ausgabeverzeichnis falls nicht vorhanden
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def extract_text_list(self, tree: etree._ElementTree, xpath: str) -> List[str]:
        """Extrahiere Liste von Texten via XPath"""
        return tree.xpath(xpath, namespaces=TEI_NS)
    
    def extract_text(self, tree: etree._ElementTree, xpath: str, default: str = '') -> str:
        """Extrahiere einzelnen Text via XPath"""
        results = tree.xpath(xpath, namespaces=TEI_NS)
        return results[0] if results else default
    
    def serialize_mixed_content(self, element: etree._Element) -> Dict[str, Any]:
        """
        Serialisiere ein XML-Element mit Mixed Content als positionserhaltende Struktur.
        
        Returns:
            {
                "content": [
                    {"type": "text", "value": "Text vor "},
                    {"type": "hi", "rend": "superscript", "value": "3"},
                    {"type": "text", "value": "Text nach"}
                ],
                "@type": "...",  # Attribute des Parent-Elements
                ...
            }
        """
        result = {}
        
        # Attribute übernehmen (ohne Namespace)
        for key, value in element.attrib.items():
            # Entferne TEI Namespace aus Attributnamen
            clean_key = key.replace('{http://www.tei-c.org/ns/1.0}', '')
            result[f"@{clean_key}"] = value
        
        # Prüfe ob Mixed Content vorliegt
        has_mixed = (element.text and element.text.strip()) or len(element) > 0
        
        if has_mixed:
            content = []
            
            # Text vor dem ersten Child
            if element.text and element.text.strip():
                content.append({
                    "type": "text",
                    "value": element.text
                })
            
            # Iteriere über Child-Elemente
            for child in element:
                # Child-Element
                child_tag = child.tag.replace('{http://www.tei-c.org/ns/1.0}', '')
                child_data = {
                    "type": child_tag,
                    "value": child.text or ""
                }
                
                # Child-Attribute
                for key, value in child.attrib.items():
                    clean_key = key.replace('{http://www.tei-c.org/ns/1.0}', '')
                    child_data[clean_key] = value
                
                content.append(child_data)
                
                # Text nach diesem Child (tail)
                if child.tail and child.tail.strip():
                    content.append({
                        "type": "text",
                        "value": child.tail
                    })
            
            result["content"] = content
        else:
            # Kein Mixed Content - nur Text
            result["value"] = element.text or ""
        
        return result

    def handle_mixed_content_elements(self, tree: etree._ElementTree) -> etree._ElementTree:
        """
        Identifiziere und markiere Elemente mit Mixed Content VOR der JSON-Konvertierung.
        Fügt ein temporäres Attribut 'mixed-content-json' mit der strukturierten Darstellung hinzu.
        """
        # Finde alle Elemente die Mixed Content haben könnten
        # Diese Liste kannst du erweitern je nachdem welche Elemente betroffen sind
        mixed_content_xpaths = [
            '//tei:note',
            '//tei:def',
            '//tei:quote',
            '//tei:cit',
            '//tei:bibl',
            '//tei:etym',
            '//tei:sense',
            # Weitere nach Bedarf...
        ]
        
        for xpath in mixed_content_xpaths:
            elements = tree.xpath(xpath, namespaces=TEI_NS)
            for elem in elements:
                # Prüfe ob wirklich Mixed Content (Text + Child-Elemente)
                has_text = elem.text and elem.text.strip()
                has_children = len(elem) > 0
                
                # Auch Kinder mit tail-Text zählen als Mixed Content
                has_tail = any(child.tail and child.tail.strip() for child in elem)
                
                if (has_text and has_children) or has_tail:
                    # Serialisiere als JSON und füge als Attribut ein
                    mixed_json = json.dumps(self.serialize_mixed_content(elem), ensure_ascii=False)
                    elem.set('mixed-content-json', mixed_json)
        
        return tree

    def clean_mixed_content_duplicates(self, data: Any) -> Any:
        """
        Entferne xmltodict-generierte Felder wenn 'content' Array existiert.
        """
        if isinstance(data, dict):
            # Wenn 'content' existiert, entferne die redundanten xmltodict-Felder
            if 'content' in data:
                # Lösche den leeren Key "" (xmltodict Text)
                data.pop('', None)
                
                # Lösche alle Child-Element Keys die jetzt in 'content' sind
                # (außer Attribute die mit @ beginnen)
                keys_to_remove = []
                for key in data.keys():
                    # Behalte nur: '@...', 'content', 'type'
                    if key not in ['content', 'type'] and not key.startswith('@'):
                        # Prüfe ob dieser Key ein Element ist das in content vorkommt
                        element_types = {item.get('type') for item in data['content'] if isinstance(item, dict)}
                        if key in element_types:
                            keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    data.pop(key, None)
            
            # Rekursiv für alle Werte
            return {k: self.clean_mixed_content_duplicates(v) for k, v in data.items()}
        
        elif isinstance(data, list):
            return [self.clean_mixed_content_duplicates(item) for item in data]
        
        return data

    def extract_mixed_content_from_json(self, data: Any) -> Any:
        """
        Durchsuche JSON rekursiv und repariere Mixed Content Nodes.
        Nutzt das 'mixed-content-json' Attribut das wir vorher eingefügt haben.
        """
        if isinstance(data, dict):
            # Prüfe ob dieses Element Mixed Content hat
            if 'mixed-content-json' in data:
                try:
                    mixed_data = json.loads(data['mixed-content-json'])
                    # Merge die strukturierten Daten
                    data.update(mixed_data)
                    # Entferne das temporäre Attribut
                    del data['mixed-content-json']
                except json.JSONDecodeError:
                    pass
            
            # Rekursiv für alle Werte
            result = {k: self.extract_mixed_content_from_json(v) for k, v in data.items()}
            
            # Bereinige Duplikate NACHDEM alles verarbeitet wurde
            result = self.clean_mixed_content_duplicates(result)
            
            return result
        
        elif isinstance(data, list):
            return [self.extract_mixed_content_from_json(item) for item in data]
        
        return data
    
    def tei_to_json(self, tree: etree._ElementTree) -> Dict[str, Any]:
        """Konvertiere TEI XML zu JSON"""
        
        # SCHRITT 1: Mixed Content Elemente vorverarbeiten
        tree = self.handle_mixed_content_elements(tree)
        
        xml_str = etree.tostring(tree, encoding='unicode')
        
        # XML Namespace-Attribute umbenennen
        xml_str = xml_str.replace('xml:id', 'xmlId').replace('xml:lang', 'xmlLang')
        
        # force_list: Diese Elemente sind IMMER Arrays
        json_data = xmltodict.parse(xml_str, attr_prefix="", cdata_key="", force_list={
            'form',
            'sense', 
            'cit',
            'usg',
            'ref',
            'bibl',
            'placeName',
            'note',
            # 'etym'
        })
        
        # SCHRITT 2: Mixed Content aus temporären Attributen extrahieren
        json_data = self.extract_mixed_content_from_json(json_data)
        
        return json_data
    
    def parse_tei_file(self, filepath: Path) -> Dict[str, Any]:
        """Parse ein TEI Lex-0 File und extrahiere alle relevanten Felder"""
        parser = etree.XMLParser(recover=True)  # Ignoriere XML-Fehler
        tree = etree.parse(str(filepath), parser)
                
        # ID extrahieren
        entry_id = self.extract_text(tree, '//tei:entry/@xml:id')
        if not entry_id:
            raise ValueError(f"No entry ID found in {filepath}")
        
        # Wörterbuch-Code
        wb = entry_id.split('__')[0] if '__' in entry_id else 'unknown'
        
        # Lemma
        lemma = self.extract_text(tree, '//tei:form[@type="lemma"]/tei:orth/text()')
        
        # Varianten
        variants = self.extract_text_list(tree, '//tei:form[@type="variant"]/tei:orth/text()')
        # Auch search forms hinzufügen
        variants.extend(self.extract_text_list(tree, '//tei:form[@type="search"]/tei:orth/text()'))
        variants = list(set(variants))  # Deduplizieren
        
        # Definitionen (alle sense/def)
        definitions = self.extract_text_list(tree, '//tei:sense/tei:def/text()')
        
        # Regionen
        regions = self.extract_text_list(tree, '//tei:usg[@type="geographic"]/text()')
        regions = list(set(regions))  # Deduplizieren
        
        # Vollständiges TEI als JSON (mit Mixed Content Handling)
        tei_json = self.tei_to_json(tree)

        # Original TEI XML als String
        tei_xml = etree.tostring(tree, encoding='unicode', pretty_print=True)
        
        # Search Text (für Volltext-Suche)
        search_parts = [lemma] + variants + definitions
        # Auch Beispiele hinzufügen
        examples = self.extract_text_list(tree, '//tei:cit[@type="example"]/tei:quote/text()')
        search_parts.extend(examples[:5])  # Max 5 Beispiele
        search_text = ' '.join(search_parts)
        
        return {
            'id': entry_id,
            'wb': wb,
            'lemma': lemma,
            'lemma_variants': variants,
            'definitions': definitions,
            'regions': regions,
            'data': tei_json,
            'tei_xml': tei_xml,
            'search_text': search_text
        }
    
    def get_relative_output_path(self, input_filepath: Path) -> Path:
        """Berechne den relativen Ausgabepfad basierend auf der Eingabestruktur"""
        # Relativen Pfad zur Input-Root berechnen
        try:
            relative_path = input_filepath.relative_to(self.input_dir)
        except ValueError:
            # Falls File nicht im input_dir liegt, nutze nur den Dateinamen
            relative_path = Path(input_filepath.name)
        
        # Ändere Extension zu .json
        relative_path = relative_path.with_suffix('.json')
        
        # Vollständiger Ausgabepfad
        output_path = self.output_dir / relative_path
        
        # Erstelle Unterverzeichnisse falls nötig
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        return output_path
    
    def convert_file(self, filepath: Path) -> bool:
        """Konvertiere ein einzelnes TEI File zu JSON"""
        try:
            data = self.parse_tei_file(filepath)
            
            # Berechne Ausgabepfad mit gleicher Verzeichnisstruktur
            output_path = self.get_relative_output_path(filepath)
            
            # Schreibe JSON-Datei
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"✗ Error converting {filepath.relative_to(self.input_dir)}: {e}")
            return False
    
    def convert_directory(self):
        """Konvertiere alle TEI Files aus dem Eingabeverzeichnis (rekursiv)"""
        # Rekursiv alle XML-Dateien finden
        tei_files = list(self.input_dir.rglob('*.xml'))
        total = len(tei_files)
        
        if total == 0:
            print(f"✗ No XML files found in {self.input_dir}")
            return
        
        print(f"Found {total} TEI files to convert")
        print(f"Input:  {self.input_dir.absolute()}")
        print(f"Output: {self.output_dir.absolute()}")
        print(f"{'='*60}")
        
        converted = 0
        failed = 0
        
        for i, filepath in enumerate(tei_files, 1):
            if self.convert_file(filepath):
                converted += 1
            else:
                failed += 1
            
            # Progress alle 100 Dateien
            if i % 100 == 0 or i == total:
                print(f"Progress: {i}/{total} (✓ {converted}, ✗ {failed})")
        
        print(f"\n{'='*60}")
        print(f"Conversion complete!")
        print(f"  Total:     {total}")
        print(f"  Converted: {converted}")
        print(f"  Failed:    {failed}")
        print(f"{'='*60}")
        
        # Statistiken
        self.print_statistics(tei_files)
    
    def print_statistics(self, tei_files: List[Path]):
        """Zeige Statistiken über die konvertierten Daten"""
        wb_stats = {}
        
        for filepath in tei_files:
            try:
                data = self.parse_tei_file(filepath)
                wb = data['wb']
                
                if wb not in wb_stats:
                    wb_stats[wb] = {
                        'count': 0,
                        'unique_lemmas': set(),
                        'total_variants': 0,
                        'total_definitions': 0
                    }
                
                wb_stats[wb]['count'] += 1
                wb_stats[wb]['unique_lemmas'].add(data['lemma'])
                wb_stats[wb]['total_variants'] += len(data['lemma_variants'])
                wb_stats[wb]['total_definitions'] += len(data['definitions'])
                
            except:
                pass
        
        if wb_stats:
            print("\nStatistics:")
            print(f"{'Dictionary':<15} {'Entries':<10} {'Unique':<10} {'Avg Vars':<10} {'Avg Defs':<10}")
            print("-" * 60)
            
            for wb, stats in sorted(wb_stats.items()):
                avg_vars = stats['total_variants'] / stats['count'] if stats['count'] > 0 else 0
                avg_defs = stats['total_definitions'] / stats['count'] if stats['count'] > 0 else 0
                
                print(f"{wb:<15} {stats['count']:<10} {len(stats['unique_lemmas']):<10} "
                      f"{avg_vars:<10.1f} {avg_defs:<10.1f}")


def main():
    """Main Entry Point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Convert TEI Lex-0 files to JSON (recursive)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Beispiele:
  {sys.argv[0]}
  {sys.argv[0]} --input ./meine_tei_dateien --output ./meine_json_dateien
  {sys.argv[0]} -i /data/tei -o /data/json

Das Skript durchsucht rekursiv alle Unterordner nach XML-Dateien und 
erstellt die gleiche Verzeichnisstruktur im Output-Ordner.

Beispiel Struktur:
  Input:   ./input_tei/dict1/entries/a.xml
           ./input_tei/dict1/entries/b.xml
           ./input_tei/dict2/c.xml
  
  Output:  ./output_json/dict1/entries/a.json
           ./output_json/dict1/entries/b.json
           ./output_json/dict2/c.json

Standardwerte (wenn keine Parameter angegeben):
  Input:  {DEFAULT_INPUT_DIR}
  Output: {DEFAULT_OUTPUT_DIR}
        """
    )
    
    parser.add_argument('-i', '--input', type=str, 
                       default=DEFAULT_INPUT_DIR,
                       help=f'Input directory containing TEI XML files (default: {DEFAULT_INPUT_DIR})')
    parser.add_argument('-o', '--output', type=str,
                       default=DEFAULT_OUTPUT_DIR,
                       help=f'Output directory for JSON files (default: {DEFAULT_OUTPUT_DIR})')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"✗ Input directory not found: {input_dir}")
        print(f"  Creating directory: {input_dir}")
        input_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Please add TEI XML files to {input_dir.absolute()} and run again.")
        sys.exit(1)
    
    # Konvertierung durchführen
    converter = TEIConverter(args.input, args.output)
    
    try:
        start_time = datetime.now()
        converter.convert_directory()
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        print(f"\nDuration: {duration:.2f} seconds")
        
    except Exception as e:
        print(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()