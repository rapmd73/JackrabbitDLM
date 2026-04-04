## Section - Non‑Technical Description

The program repeatedly tries to gain exclusive access to a shared storage area so it can read a number kept there, possibly increase that number by one every few attempts based on chance, and records how often it succeeds or fails in obtaining that access.



## Section - Technical Analysis

The script begins by importing several standard library modules (`sys`, `os`, `time`, `json`, `random`) and appending `/home/GitHub/JackrabbitDLM` to the module search path so that the custom module `DLMLocker` can be imported under the alias **DLM**. Two command‑line arguments influence its behavior: an optional integer supplied as the first positional argument sets the target iteration count **m** (default = *​​​​​​​​​​​​* * * * * * * * *), while presence of the strings *aggressive* and *locks* toggles Boolean flags **RetryLocker** (‑False when *aggressive* appears) and **TestMemory** (‑False when *locks* appears).

Three integer counters are initialized (**c**, **f**, **s**, **r**, **w**) representing respectively an internal value tracker for memory operations,
failed lock acquisitions,
successful lock acquisitions,
read operations,
and write operations.
A floating‑point value **wv** drawn uniformly from [0 - ] determines later write probability thresholds.
Two locker objects are created via calls into **DLMLocker**:
- **fw₁** (`DLM.Locker('LockerTest', Timeout=..., Retry=`...)) represents "the framework" used for acquiring locks;
- **Memory** (`DLM.Locker('LockFighter', ID='LockFighterMemory')`) represents "the data store" where key‑value pairs are persisted.
Immediately afterwards an authentication check (`fw₁.IsDLM()`) verifies that an underlying service named JackrabbitDLM is reachable; otherwise an error message prints and execution terminates with exit status ¹⁰¹⁰¹⁰¹⁰¹⁰¹⁰¹⁰¹⁰¹⁰¹²³³³³³³³³³³³³***???***.

Inside each iteration of while-loop conditioned on (**c < m**), one of two possible locking strategies selects based on flag state (**RetryLocker**). When true (**RetryLocker**), method call (**fw₁.Lock(expire=`...**) obtains an exclusive lease employing internal retry logic;
when false (**RetryLocker**), method call (**fw₁.IsLocked(expire=`...**) simply tests whether another process currently holds such lease without attempting retries.
If returned string equals `'locked'` indicating successful acquisition,
control enters protected section guarded by generic exception handling.
Within this section,
a read operation retrieves current payload via (**Memory.Get()**) incrementing read counter (**r**). If payload contains key `'DataStore'` its value parsed into integer overwrites local variable (**c**). Otherwise payload considered absent - implying initial state - local variable remains unchanged.
Subsequently independent uniform draw decides whether current iteration performs write operation according threshold derived earlier from stored float value rounded two decimal places plus condition ensuring target limit not yet exceeded;
on success local counter increments before persisting updated numeric string back into store through call (**Memory.Put(data=str(c), expire=`...**) raising write counter (**w**). In case payload lacked `'DataStore'` key unconditional write occurs similarly increasing both local counter & writer count irrespective threshold test regardless outcome above scenario leading always incrementation & persistence attempt whenever entry missing initially present nonexistent entry case leads immediate creation attempt regardless probability check due absence guard clause earlier branch ensures writing occurs anyway once found missing entry detection triggers unconditional insertion path separate conditional branch preceding probability test ensures writes happen only when entry existed already present thus distinguishing between creation vs update pathways though both result identical effect storing incremented numeric representation back into store updating writer metric accordingly .
Regardless outcome above branch executes optional junk generation sub‑routine contingent upon flag TestMemory being true;
here another uniform draw determines whether auxiliary locker object instantiated either bearing name suffix colon appended framework identifier plus supplied constant strings N/I representing attacker role versus benign role respectively ; further nested draws decide whether large random byte blob generated via os·urandom sized between ninety-six kilobytes multiplied factor ten twenty-four up five hundred twelve kilobytes inserted temporarily into auxiliary locker's storage expiring ten seconds later ; subsequent independent draw decides whether auxiliary locker's contents erased immediately thereafter cleaning up garbage produced during this inner sub‑routine .
Regardless success failure within protected section successful path increments success counter (*s*) whereas any raised exception caught increments failure counter (*f*) prints traceback optionally pauses tenth second when retry enabled before proceeding onward ;
after exiting protected region irrespective outcome unlocking call executed releasing held lease allowing other contenders opportunity acquire same resource next cycle .
When acquisition attempt fails i.e returned string differs `'locked'` failure counter increments similarly optional tenth second pause applied contingent upon retry enabled flag .

Loop repeats until locally tracked value reaches preset limit m at which point elapsed wall clock time captured , contention ratio calculated proportion failures divided total attempts multiplied hundred rounded two decimal places , final line printed comprising : first character textual representation boolean flag indicating retry mode enabled/disabled , process identifier obtained via os·getpid , elapsed duration formatted eight digits precision decimal point , followed sequentially integers counts failures successes reads writes contention ratio percentage final internal numeric value reached upon termination .