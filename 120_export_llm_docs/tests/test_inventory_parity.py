import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
from example_generator import build_example_filenames


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding='utf-8')
    return path


def test_loader_uses_unique_phase20_member_inventory(tmp_path):
    phase20 = _write(tmp_path / 'members.xml', '''
<Types>
  <Type><Name>ITest</Name><Assembly>A</Assembly><Namespace>N</Namespace>
    <PublicProperties><Property><Name>First</Name><Url>first.htm</Url></Property></PublicProperties>
    <PublicMethods><Method><Name>Run</Name><Url>run.htm</Url></Method></PublicMethods>
  </Type>
  <Type><Name>ITest</Name><Assembly>A</Assembly><Namespace>N</Namespace>
    <PublicProperties><Property><Name>First</Name><Url>first.htm</Url></Property>
      <Property><Name>Second</Name><Url>second.htm</Url></Property></PublicProperties>
  </Type>
</Types>
''')
    phase40 = _write(tmp_path / 'types.xml', '<Types/>')
    phase50 = _write(tmp_path / 'details.xml', '''
<Members>
  <Member><Type>N.ITest</Type><Name>First</Name><Signature>First {get;}</Signature>
    <Description>First property</Description></Member>
</Members>
''')
    phase60 = _write(tmp_path / 'enums.xml', '<Enums/>')
    phase80 = _write(tmp_path / 'examples.xml', '<Examples/>')

    types = DataLoader().load_all(
        str(phase20), str(phase40), str(phase50), str(phase60), str(phase80)
    )

    type_info = types['N.ITest']
    assert [item.name for item in type_info.properties] == ['First', 'Second']
    assert [item.name for item in type_info.methods] == ['Run']
    assert type_info.properties[0].description == 'First property'
    assert type_info.properties[1].description == ''


def test_example_filenames_preserve_colliding_urls():
    urls = {
        'sldworksapi/Create_Motion_Example_CSharp.htm',
        'swmotionstudyapi/Create_Motion_Example_CSharp.htm',
        'sldworksapi/Unique_Example_CSharp.htm',
    }

    filenames = build_example_filenames(urls)

    assert len(filenames) == len(urls)
    assert len(set(filenames.values())) == len(urls)
    assert filenames['sldworksapi/Unique_Example_CSharp.htm'] == 'Unique_Example_CSharp.md'
    assert filenames['sldworksapi/Create_Motion_Example_CSharp.htm'].endswith(
        '__Create_Motion_Example_CSharp.md'
    )
