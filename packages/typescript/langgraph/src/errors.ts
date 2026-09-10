export class UnsupportedLangGraphVersionError extends Error {
  readonly installedVersion: string;
  readonly supportedRange: string;
  readonly testedVersions: readonly string[];

  constructor(options: {
    installedVersion: string;
    supportedRange: string;
    testedVersions: readonly string[];
  }) {
    const tested = options.testedVersions.join(", ");
    super(
      `Unsupported LangGraph.js version ${options.installedVersion}. ` +
        `@agent-topology/langgraph has extraction evidence only for ${tested}. ` +
        `Install a tested release with \`npm install @langchain/langgraph@${options.supportedRange}\`.`,
    );
    this.name = "UnsupportedLangGraphVersionError";
    this.installedVersion = options.installedVersion;
    this.supportedRange = options.supportedRange;
    this.testedVersions = [...options.testedVersions];
  }
}
