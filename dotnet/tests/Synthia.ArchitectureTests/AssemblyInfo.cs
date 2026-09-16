// The routing-table fixture boots the application, and configuration reaches it through
// process-global environment variables (see ArchitectureApiFactory). Serialising the assembly
// keeps two differently-configured boots from reading each other's settings.
[assembly: CollectionBehavior(DisableTestParallelization = true)]
