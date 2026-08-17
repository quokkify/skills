interface ExtensionAPI {
    registerCommand(name: string, command: CommandDefinition): void;
    getSetting(key: string): any;
    setSetting(key: string, value: any): void;
    notify(message: string, level?: "info" | "warning" | "error"): void;
    bash(command: string, options?: BashOptions): Promise<BashResult>;
    log(level: "debug" | "info" | "warn" | "error", message: string): void;
}
interface CommandDefinition {
    description: string;
    handler: (args: string, ctx: CommandContext) => Promise<string | void>;
    getArgumentCompletions?: (prefix: string) => string[] | null;
}
interface CommandContext {
    ui: {
        notify(message: string, level: "info" | "warning" | "error"): void;
        select(title: string, items: string[]): Promise<string | null>;
        confirm(title: string, message: string): Promise<boolean>;
    };
    session: any;
}
interface BashOptions {
    cwd?: string;
    env?: Record<string, string>;
    timeout?: number;
    signal?: AbortSignal;
}
interface BashResult {
    stdout: string;
    stderr: string;
    exitCode: number;
    signal?: string;
}
export default function (pi: ExtensionAPI): void;
export {};
//# sourceMappingURL=index.d.ts.map