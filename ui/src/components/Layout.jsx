import { Link, Outlet } from 'react-router-dom';

function BrandMark() {
    return (
        <svg
            width="28"
            height="28"
            viewBox="0 0 32 32"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
            className="shrink-0"
        >
            <rect width="32" height="32" rx="8" className="fill-primary" />
            <path
                d="M9 21c2.5-1.6 3.5-4 5-7s3-5.5 5.5-7"
                className="stroke-primary-foreground"
                strokeWidth="2"
                strokeLinecap="round"
            />
            <circle cx="9" cy="21" r="2.2" className="fill-primary-foreground" />
            <circle cx="22" cy="9" r="2.2" className="fill-primary-foreground" />
        </svg>
    );
}

function Layout() {
    return (
        <div className="min-h-screen bg-background text-foreground">
            <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-sm">
                <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-4">
                    <Link to="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-80">
                        <BrandMark />
                        <div className="flex flex-col leading-none">
                            <span className="text-base font-semibold tracking-tight">Filament</span>
                            <span className="text-[11px] text-muted-foreground">Durable task observability</span>
                        </div>
                    </Link>
                    <a
                        href="https://github.com/pyfilament/pyfilament"
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-muted-foreground transition-colors hover:text-foreground"
                    >
                        Docs
                    </a>
                </div>
            </header>
            <main className="mx-auto w-full max-w-5xl px-4 py-6">
                <Outlet />
            </main>
        </div>
    );
}

export default Layout;
