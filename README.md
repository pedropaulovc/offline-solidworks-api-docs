# Offline SolidWorks API Documentation

**Enhanced IntelliSense and AI-Assisted Development for SolidWorks API**

This project provides two comprehensive documentation packages for the SolidWorks API:

1. **XMLDoc Package** - Visual Studio IntelliSense support with tooltips, parameter info, and examples
2. **LLM Documentation Package** - AI-optimized markdown documentation for use with Claude, ChatGPT, and other LLMs

## Quick Start

### Option 1: LLM Documentation for AI-Assisted Development

**Use with Claude, ChatGPT, Cursor, or other AI coding assistants:**

1. **Download** the latest LLM docs package from [releases](https://github.com/pedropaulovc/offline-solidworks-api-docs/releases/latest)
   - File: `SolidWorks.Interop.llms.v{version}.zip`

2. **Extract** the ZIP file to your preferred location

3. **Use with your AI assistant**:
   - **Claude Code**: Point to the extracted folder as context
   - **Cursor**: Add to workspace and use `@docs` to reference
   - **ChatGPT**: Upload relevant markdown files for context
   - **Manual search**: Use grep/ripgrep to find specific APIs

### Option 2: XMLDoc for Visual Studio IntelliSense

**Get IntelliSense tooltips and documentation in Visual Studio:**

1. **Download** the latest XMLDoc package from [releases](https://github.com/pedropaulovc/offline-solidworks-api-docs/releases/latest)
   - File: `SolidWorks.Interop.xmldoc.v{version}.zip`

2. **Extract** the ZIP file to get 14 XML files:
   ```
   SolidWorks.Interop.dsgnchk.xml
   SolidWorks.Interop.examples.xml
   SolidWorks.Interop.guides.xml
   SolidWorks.Interop.sldtoolboxconfigureaddin.xml
   SolidWorks.Interop.sldworks.xml
   SolidWorks.Interop.sw3dprinter.xml
   SolidWorks.Interop.swbrowser.xml
   SolidWorks.Interop.swcommands.xml
   SolidWorks.Interop.swconst.xml
   SolidWorks.Interop.swdimxpert.xml
   SolidWorks.Interop.swhtmlcontrol.xml
   SolidWorks.Interop.swmotionstudy.xml
   SolidWorks.Interop.swpublished.xml
   SolidWorks.Interop.swscanto3d.xml
   ```

3. **Copy** the XML files to your SolidWorks SDK DLL location:
   - **SOLIDWORKS 3DEXPERIENCE**: `C:\Program Files\Dassault Systemes\SOLIDWORKS 3DEXPERIENCE\SOLIDWORKS\api\redist`
   - **Standard SOLIDWORKS**: `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist`

4. **Restart** Visual Studio

5. **Enjoy!** Hover over any SolidWorks API type or method to see full documentation

## What's Included

### XMLDoc Package (~2 MB compressed, ~15 MB uncompressed)

Contains XML files providing IntelliSense documentation for all SolidWorks API assemblies, plus companion semantic catalogs:

- **Comprehensive coverage**: 2,518 types, 11,523 members
- **Full descriptions**: Type and member documentation
- **Parameter details**: Complete parameter information
- **Return values**: Detailed return type documentation
- **Code examples**: 3,708+ examples (VBA, C#, VB.NET, C++)
- **Remarks**: Usage notes and best practices
- **Complete signatures**: Namespaced `sw:signature` elements retain return types, parameter types, and property accessors
- **Multilingual examples**: `SolidWorks.Interop.examples.xml` catalogs VBA, VB.NET, C++ COM, and C# examples with language metadata
- **Programming guide**: `SolidWorks.Interop.guides.xml` embeds the programming/how-to Markdown pages

### LLM Documentation Package (~50 MB compressed, ~200 MB uncompressed)

Contains 26,902 markdown files optimized for AI consumption:

#### Folder Structure

```
📁 solidworks-docs/ (extracted from `SolidWorks.Interop.llms.v{version}.zip`)
├── 📄 README.md                    # Guide for using with LLMs
│
├── 📁 types/                       # API Types (1,563 types)
│   ├── 📁 IModelDoc2/              # One folder per type
│   │   ├── _overview.md            # Type description, remarks, counts
│   │   ├── CreateArc.md            # Individual method documentation
│   │   ├── CreateArc2.md
│   │   ├── Save.md
│   │   ├── GetPathName.md          # Individual property documentation
│   │   └── ... (721 members)
│   ├── 📁 ISldWorks/
│   │   ├── _overview.md
│   │   └── ... (methods and properties)
│   └── ... (1,563 type folders)
│
├── 📁 enums/                       # Enumerations (955 enums)
│   ├── 📁 swDocumentTypes_e/
│   │   ├── _overview.md
│   │   ├── swDocPART.md            # Part document type
│   │   ├── swDocASSEMBLY.md        # Assembly document type
│   │   └── swDocDRAWING.md         # Drawing document type
│   └── ... (955 enum folders)
│
├── 📁 index/                       # Navigation & Discovery
│   ├── by_category.md              # Types by functional category
│   ├── by_assembly.md              # Types by .NET assembly
│   └── statistics.md               # Quick stats and largest types
│
├── 📁 examples/                    # Code Examples (3,708 examples)
│   ├── Create_Advanced_Hole_Example_CSharp.md
│   ├── Create_Assembly_Example_VBA.md
│   └── ... (all examples, flat structure)
│
└── 📁 docs/                        # Programming Guide (125 pages)
    ├── Overview.md
    ├── SOLIDWORKS Partner Program.md
    └── 📁 Programming with the SOLIDWORKS API/
        ├── Getting Started.md
        ├── Object Model.md
        └── ... (hierarchical structure)
```

#### Key Features

- **File-per-member**: Each method, property, and enum gets its own file (easy to grep/search)
- **YAML frontmatter**: Machine-readable metadata in every file
- **Simplified links**: `[[IModelDoc2]]` instead of XML-style cross-references
- **Flat structure**: `types/TypeName/` instead of deep nesting
- **Index files**: Browse by category or assembly
- **Full examples**: Complete code samples with syntax highlighting
- **Programming guide**: Comprehensive tutorials and best practices

## Usage Examples

### Using LLM Docs with AI Assistants

#### With Claude Code

```bash
# Add to your project context
claude --context /path/to/SolidWorks.LLM.Docs

# Then ask questions
"How do I create an arc in a SolidWorks sketch?"
"Show me examples of working with assemblies"
```

#### With Cursor

1. Add the LLM docs folder to your workspace
2. Use `@docs` to reference documentation:
   ```
   @docs How do I save a SolidWorks document?
   ```

#### Manual Grep/Search

```bash
# Find all CreateArc methods
grep -r "CreateArc" types/IModelDoc2/

# Find methods in a specific category
grep -l "category: Assembly Interfaces" types/*/_.overview.md

# Search examples for specific topics
grep -r "advanced hole" examples/

# Find all methods that return a specific type
grep -r "Returns.*ISketchArc" types/
```

### Using XMLDoc in Visual Studio

Once installed, you'll see documentation when:

- **Hovering** over types and members
  ```csharp
  ISldWorks swApp = ...;  // Hover shows: "Allows access to top-level SolidWorks functionality"
  ```

- **Writing code** with IntelliSense
  ```csharp
  IModelDoc2 model = swApp.  // IntelliSense shows all methods with descriptions
  ```

- **Viewing parameters**
  ```csharp
  model.CreateArc2(  // Parameter tooltip shows each parameter's purpose
  ```

## Common Use Cases

### Finding the Right API

**Problem**: "I want to create a hole feature, but don't know which API to use"

**Solution**:
1. Check `index/by_category.md` for "Feature Interfaces"
2. Look for hole-related types
3. Read the `_overview.md` for each type
4. Check `examples/` for hole creation examples

### Understanding Parameters

**Problem**: "What does the `Options` parameter in `SaveAs3` mean?"

**Solution**:
1. Open `types/IModelDoc2/SaveAs3.md`
2. Read the parameter descriptions
3. Check remarks for usage notes
4. Look for examples showing `SaveAs3` usage

### Learning from Examples

**Problem**: "How do I properly initialize a SolidWorks connection?"

**Solution**:
1. Search `examples/` for initialization patterns
2. Look at multiple language examples (C#, VBA, VB.NET)
3. Check `docs/Getting Started.md` for tutorials

## Documentation Quality

### Coverage Statistics

- **Types**: 2,518 total
  - With descriptions: ~1,568 (93%)
  - With examples: ~561 (33%)
  - With remarks: ~455 (27%)

- **Members**: 11,523 total
  - Methods with parameters: ~8,000+
  - Properties with descriptions: ~3,000+
  - All with return value documentation

- **Examples**: 3,708 total
  - C#: ~1,100
  - VBA: ~1,000
  - VB.NET: ~900
  - C++: ~700

- **Programming Guide**: 125 pages
  - Tutorials and walkthroughs
  - Best practices
  - Architecture documentation

## Building From Source

Want to regenerate the documentation yourself or contribute improvements?

See **[DEVELOPING.md](DEVELOPING.md)** for:
- Complete pipeline architecture (13 phases)
- Setup and installation instructions
- Running the crawlers and extractors
- Testing and validation
- Contributing guidelines

## Legal Notice

**IMPORTANT**: This tool is for personal, educational, and fair use only.

- **You may**: Use these packages for personal development with SolidWorks API
- **You may**: Share these generated packages (XMLDoc and LLM docs)
- **You must not**: Use for commercial redistribution
- **You must not**: Claim ownership of SolidWorks documentation

The SolidWorks API documentation content is copyrighted by **Dassault Systèmes SolidWorks Corporation**. These packages are generated under fair use for educational purposes.

## License

- **Pipeline code**: MIT License (see LICENSE file)
- **Documentation content**: Copyright Dassault Systèmes SolidWorks Corporation

## Contributing

Contributions welcome! See [DEVELOPING.md](DEVELOPING.md) for:
- How to set up the development environment
- Running the pipeline
- Adding new features
- Submitting improvements

## Additional Resources

- **SolidWorks API Help**: https://help.solidworks.com/2026/english/api/
- **Issues & Feedback**: https://github.com/pedropaulovc/offline-solidworks-api-docs/issues
- **Developer Guide**: [DEVELOPING.md](DEVELOPING.md)

## Acknowledgments

This project makes SolidWorks API development easier by providing:
- Offline documentation access
- Enhanced IDE integration
- AI-assisted development capabilities
- Searchable, well-organized reference materials

Built with respect for Dassault Systèmes' documentation and the developer community.

---

**Version**: Check [releases](https://github.com/pedropaulovc/offline-solidworks-api-docs/releases) for latest version
**Last Updated**: 2025-11-23
