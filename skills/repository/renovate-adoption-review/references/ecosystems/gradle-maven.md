# Gradle and Maven

## Where to look in the update

- Gradle: the release notes and the upgrade guide for the target version (deprecations, removed APIs, configuration-cache and toolchain changes).
- Gradle and Maven plugins: plugin release notes and CHANGELOG for renamed extension properties, task names, and DSL blocks.
- Libraries: release notes, migration guide, and the tag-to-tag diff of the public API (`@Deprecated` additions with a named replacement, removed classes).

## Consumer files to grep

- `build.gradle(.kts)`, `settings.gradle(.kts)`, `gradle.properties`, `buildSrc/**`, convention plugins under `build-logic/**`, `gradle/libs.versions.toml`, `gradle/wrapper/gradle-wrapper.properties`.
- `pom.xml`, `.mvn/**`, parent POMs in the repository.
- Source files using the library's deprecated types or methods (`src/**/*.java`, `src/**/*.kt`).

## Local warning command

- `./gradlew build --warning-mode all` (or the consumer's documented task with `--warning-mode all`): prints each deprecation with the file and the replacement.
- Compiler deprecation output: `-Xlint:deprecation` for `javac`, Kotlin compiler warnings.
- Maven: `mvn -B verify` warnings, and plugin deprecation messages in the log.

## Typical adoptable patterns

- A deprecated DSL property or method with a documented replacement (lazy `Property` APIs replacing eager setters, renamed extension properties).
- Hand-rolled JDK selection (`sourceCompatibility` plus manual `JAVA_HOME` handling) when the consumer already targets a version and the toolchain API is documented for that use.
- A workaround task or `afterEvaluate` hook that the new plugin version replaces with a documented option.
- A deprecated library method with a named successor in its `@Deprecated` Javadoc or release notes.
- Wrapper or plugin version comments in docs.

## Typical false positives

- Deprecation warnings emitted by third-party plugins rather than the consumer's build scripts: report, do not edit the plugin.
- Toolchain adoption that changes which JDK the build uses: that is a behavior change, not a simplification, unless the version stays identical.
- Moving dependencies into a version catalog: unrelated refactor.
- Public API changes of the consumer library to follow a dependency's rename: forbidden.
