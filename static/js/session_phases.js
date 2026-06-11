(function () {
    "use strict";

    function getPhases() {
        return window.grillkitSessionPhases || null;
    }

    window.grillkitSessionPhaseNav = {
        hasPendingCodingPhase: function () {
            const phases = getPhases();
            return (
                phases &&
                phases.hasCoding &&
                !phases.codingComplete &&
                phases.sessionMode === "theory_then_coding"
            );
        },
        hasPendingTheoryPhase: function () {
            const phases = getPhases();
            return (
                phases &&
                phases.hasTheory &&
                !phases.theoryComplete &&
                phases.sessionMode === "coding_then_theory"
            );
        },
        continueToNextPhase: function () {
            window.location.reload();
        },
    };
})();
