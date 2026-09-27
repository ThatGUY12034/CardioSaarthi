import RoleCard from "../components/RoleCard";

export default function RoleSelection() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-12">
      <div className="text-center animate-fade-in-up">
        <p className="text-xs uppercase tracking-[0.2em] text-brand-muted mb-3">
          Welcome to CardioSaarthi
        </p>
        <h1 className="text-4xl font-extrabold tracking-tight">
          Choose Your <span className="text-gradient">Role</span>
        </h1>
        <p className="text-brand-muted mt-3">Select how you want to continue</p>
      </div>

      <div className="grid md:grid-cols-3 gap-6 mt-12 w-full max-w-5xl">
        <RoleCard
          icon="🎓"
          title="Student"
          subtitle="Learn & practice ECG interpretation"
          role="STUDENT"
          gradient="bg-gradient-to-br from-blue-600/20 via-blue-800/10 to-transparent border border-blue-500/20"
          accentColor="text-blue-400"
        />
        <RoleCard
          icon="👨‍🏫"
          title="Faculty"
          subtitle="Review cases & monitor students"
          role="FACULTY"
          gradient="bg-gradient-to-br from-emerald-600/20 via-emerald-800/10 to-transparent border border-emerald-500/20"
          accentColor="text-emerald-400"
        />
        <RoleCard
          icon="🧑‍⚕️"
          title="Patient"
          subtitle="Understand your ECG report"
          role="PATIENT"
          gradient="bg-gradient-to-br from-pink-600/20 via-pink-800/10 to-transparent border border-pink-500/20"
          accentColor="text-pink-400"
        />
      </div>
    </div>
  );
}